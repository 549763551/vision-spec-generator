"""光源方案推荐（规则引擎，不是"自动打光"）。

依据：行业通用选型方法CST 光源培训
   什么才算一张好图：特征与背景灰度差 ≥ 30、整体均匀、色彩还原真实
   亮场/暗场、光的四种归宿（镜面反射→同轴、漫反射→暗场、吸收、透射→背光）
  起 类型选择：方向（背光/低角度/高角度/同轴/无影）→ 偏振 → 光强
   五步思路 + 检查清单

重要边界：本模块只输出"该用什么光源"的方案建议，不控制物理光源。
若现场有可编程控制器（CST DPS 的 B/C 版带串口/网口），才谈得上闭环调光。
"""

from dataclasses import dataclass, field


# 任务类型 → (方向, 具体形态, 型号代码, 选型要点)
# 形态与型号代码取自课程「光源种类与命名规则」：RS 环形 / BS 条形 / FS·HFS 面光 /
# CO 同轴 / DS 圆顶（无影）/ LPG 线光 / TUG 隧道。
TASK_TO_LIGHT = {
    "尺寸测量":       ("背光",   "面光源（底部面光）", "HFS",  "灯珠朝上、亮度与均匀性最好；按发光区尺寸选，大于视野 20%"),
    "轮廓定位":       ("背光",   "面光源（底部面光）", "HFS",  "剪影最干净，边缘对比度最高；面光也常被直接叫背光"),
    "透明件内部缺陷": ("背光",   "平行面光源",         "PHFS", "平行光减少发散，内部气泡杂质的阴影更锐"),
    "表面划痕":       ("低角度", "环形光（小角度）",   "RS",   "发光角 30° 或 0°；角度越小越贴表面斜打，暗场才出划痕"),
    "凹坑压痕":       ("低角度", "环形光 30°",        "RS",   "暗场靠入射角等于反射角，光源要装低，装高就变亮场"),
    "异物脏污":       ("低角度", "条形光",            "2BS",  "两条可对射也可拉开避机构，角度靠安装架设调，最灵活"),
    "平面字符":       ("高角度", "环形光 90°",        "RS",   "亮场，字暗底亮；90° 直下打，装高一点光更亮"),
    "二维码":         ("高角度", "环形光 90°",        "RS",   "亮场基础上用颜色加减法拉对比度"),
    "高反光金属":     ("同轴",   "同轴光",            "CO",   "45° 半透半反镜，亮度损失一半，曝光时间要相应加长"),
    "曲面圆柱":       ("无影光", "圆顶光",            "DS",   "半球腔漫反射出光，消除曲面起伏造成的阴影与亮斑"),
    "颜色判别":       ("高角度", "环形光 90°（白光）", "RS",   "白光保证白平衡，偏色会让颜色判据整体失效"),
}

# 线扫场景另有专门光源：线光 LPG / 同轴线光 2CULPG / 隧道光 TUG，
# 配线阵相机逐行扫描，单行曝光常在 30~120 μs，功率大、多带风扇。

# 互补色表：想让某色消失就用它的互补色打光（通行做法"颜色加减法"）
COMPLEMENT = {
    "红": "青", "青": "红",
    "绿": "品红", "品红": "绿",
    "蓝": "黄", "黄": "蓝",
    "白": "白", "黑": "白",
}


@dataclass
class LightSpec:
    direction: str
    field_type: str          # 亮场 / 暗场
    color: str
    size_mm: tuple
    polarization: bool
    form: str = ""           # 具体形态：环形光 / 条形光 / 面光源 / 同轴光 / 圆顶光 …
    series: str = ""         # 型号代码：RS / 2BS / HFS / CO / DS …
    angle: str = ""          # 环形光的发光角度
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def recommend_light(task: str, fov_w: float, fov_h: float,
                    boost_color: str = "", suppress_color: str = "",
                    diag: dict | None = None,
                    install_height_limited: bool = False,
                    surface: str = "") -> LightSpec:
    """给出光源方案。

    参数
      task            : 检测任务类型，取自 TASK_TO_DIRECTION 的键
      fov_w, fov_h    : 视野 mm（决定光源发光面尺寸）
      boost_color     : 需要突出的颜色（用同色光打亮）
      suppress_color  : 需要压掉的颜色（用互补色打暗）
      diag            : 图像诊断结果（可选），用于追加修正建议
      install_height_limited : 机台限高，需要转角同轴等替代结构
      surface         : 工件表面：平整 / 曲面 / 高反光 / 镜面（默认按平整处理）

    重要修正：任务名只描述"检什么"，不描述"工件长什么样"。平面字符若落在
    曲面亮盖上，90° 直下打会产生镜面强反光。这里允许 surface 显式声明，
    也允许 diag 的过曝+边缘偏软反推疑似曲面反光，把光路改到 30°~45° 低角度。
    """
    steps = []
    warnings = []

    # --- 1. 方向 ---
    if task in TASK_TO_LIGHT:
        direction, form, series, tips = TASK_TO_LIGHT[task]
        reason = tips
    else:
        direction, form, series, tips = "高角度", "环形光 90°", "RS", "任务未匹配专用规则，按平整表面处理"
        warnings.append(f"任务类型「{task}」没有对应规则，建议人工确认光路")
    steps.append(f"检测任务「{task}」→ {form}（{series}），方向 {direction}：{tips}")
    angle = ("90°" if direction == "高角度" else ("30°" if direction == "低角度" else ""))

    # --- 1b. 表面形状 / 反光修正 ---
    # 任务名只说"检什么"，不说"工件是什么面"。高角度 90° 是按平整漫反射面外推的，
    # 弧面亮盖上会形成镜面强反光；诊断过曝 + 边缘偏软时也按同一逻辑修正。
    # 这一步让"看图说话"真正回写光路，而不是只写一条警告。
    glossy_tasks = ("平面字符", "二维码", "颜色判别")
    surface_key = (surface or "").strip()
    curved_or_glossy = surface_key in (
        "曲面", "弧面", "曲面弧面", "高反光", "高反光面", "镜面", "亮面",
    )
    diag_over = diag.get("overexposed_ratio") if diag else None
    diag_lap = diag.get("lap_var") if diag else None
    diag_suspect = (
        task in glossy_tasks
        and diag_over is not None and diag_over > 0.03
        and diag_lap is not None and diag_lap < 15
    )

    if direction == "高角度" and (curved_or_glossy or diag_suspect):
        old = f"{direction} · {form}（{angle}）"
        if diag_suspect and not curved_or_glossy:
            basis = (
                f"图像过曝 {diag_over:.1%} 且拉普拉斯方差 {diag_lap:.0f}，"
                f"疑似曲面亮面镜面反射/角度过正"
            )
        else:
            basis = f"工件表面声明为「{surface_key}」"
        direction = "低角度"
        form = "环形光 30°~45°（低角度掠射）"
        series = "RS"
        angle = "30°~45°"
        steps.append(
            f"表面修正：{basis}；90° 直下打会在弧面亮面形成镜面强反光、局部过曝，"
            f"由 {old} 改为 {form}，避开镜头直射方向；发光面尺寸仍按视野×1.2"
        )

    # --- 2. 亮场 / 暗场 ---
    field_map = {
        "背光": "亮背景（透射）",
        "低角度": "暗场（背景暗、特征亮）",
        "高角度": "亮场（背景亮、特征暗）",
        "同轴": "亮场（镜面反射）",
        "无影光": "亮场（漫射均匀）",
    }
    field_type = field_map[direction]
    steps.append(f"场型：{field_type}")
    if direction == "低角度":
        steps.append("暗场返回光少，达到同样亮度需要更高光强或更长曝光")

    # --- 3. 颜色 ---
    if boost_color and boost_color in COMPLEMENT:
        color = boost_color
        steps.append(f"颜色：要突出「{boost_color}」→ 用同色光打亮，该色变白、其余变暗（颜色加减法）")
    elif suppress_color and suppress_color in COMPLEMENT:
        color = COMPLEMENT[suppress_color]
        steps.append(f"颜色：要压掉「{suppress_color}」→ 用互补色 {color} 光，该色吸收变黑")
    else:
        color = "白光"
        steps.append("颜色：未指定颜色目标 → 白光，保证色彩还原与白平衡")

    # --- 4. 尺寸（经验值：发光面覆盖视野并留余量）---
    size_w = round(fov_w * 1.2, 1)
    size_h = round(fov_h * 1.2, 1)
    steps.append(
        f"尺寸：发光面 ≥ 视野×1.2 = {size_w}×{size_h} mm"
        f"（经验余量；远心镜头与 FA 镜头的光源尺寸不可套用同一套参数）"
    )

    # --- 5. 偏振 ---
    polarization = False
    if (
        (direction in ("同轴", "高角度") and task in ("高反光金属", "平面字符", "二维码", "颜色判别"))
        or curved_or_glossy or diag_suspect
    ):
        polarization = True
        steps.append("偏振：镜面/高反光面建议加起偏器+检偏器，旋转检偏器压掉特定方向的强反光")

    # --- 6. 安装限制 ---
    if install_height_limited:
        steps.append("机台限高 → 可用转角同轴（CO 结构），光从侧面进入再转向垂直照工件")

    # --- 7. 用图像诊断结果做修正（这是"看图说话"的落点）---
    if diag:
        diff = diag.get("gray_diff")
        over = diag.get("overexposed_ratio")
        under = diag.get("underexposed_ratio")
        sharp = diag.get("lap_var")
        strong = diag.get("strong_edge_ratio")
        if diff is not None:
            if diff < 30:
                warnings.append(
                    f"当前图像特征/背景灰度差 {diff:.1f} < 30，按通行做法判据属于不合格图，"
                    f"换光前先别调算法"
                )
            else:
                steps.append(f"当前图像灰度差 {diff:.1f} ≥ 30，对比度达标")
        if over is not None and over > 0.02:
            if curved_or_glossy or diag_suspect:
                advice = "已改低角度+偏振；若仍过曝，再降亮度或加漫射板"
            else:
                advice = "降亮度、加漫射板或上偏振"
            warnings.append(
                f"过曝像素占 {over:.1%}，细节已丢失：{advice}，不要靠调低曝光硬压"
            )
        if under is not None and under > 0.10:
            warnings.append(
                f"欠曝像素占 {under:.1%}，暗场尤其费光：提高光强或延长曝光，"
                f"加增益会同时放大噪声"
            )
        if sharp is not None and sharp < 15 and (strong is None or strong < 0.002):
            warnings.append(
                f"拉普拉斯方差 {sharp:.0f} 偏低、强边缘占比不足："
                f"可能是离焦、光源角度过正或镜头解析力不足，"
                f"先用标定板/刀口排除镜头因素再换光"
            )

    return LightSpec(
        direction=direction, field_type=field_type, form=form, series=series,
        angle=angle,
        color=color, size_mm=(size_w, size_h), polarization=polarization,
        steps=steps, warnings=warnings,
    )
