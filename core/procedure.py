"""检测流程作业指导书：把选型结果翻译成功能节点链。

为什么是"作业指导书"而不是"自动搭流程"：
  直接操作视觉软件要 SDK、要授权、要连运行中的实例，现场部署时不一定满足；
  出一份节点链加参数表，任何版本的软件、任何品牌的软件都能照着搭。

节点名用通用叫法并附常见别名，所以不绑某一家：
  图像源 / 模板定位 / 二值化 / 颗粒分析 / 直线查找 / 构造交点 / 点距 / 数据判定 / 结果输出

关键在参数有出处——每个值都能追到选型结果或图像诊断，不是拍脑袋填的。
"""

from dataclasses import dataclass, field

from .camera import task_requires_color


@dataclass
class Step:
    no: int
    node: str
    params: list = field(default_factory=list)   # [(参数名, 值, 出处)]
    note: str = ""


# 任务 → 节点链骨架（节点名，是否带参）
CHAINS = {
    "尺寸测量": ["图像源", "模板定位", "直线查找", "直线查找", "构造交点", "点距", "数据判定", "结果输出"],
    "轮廓定位": ["图像源", "模板定位", "构造坐标系", "结果输出"],
    "透明件内部缺陷": ["图像源", "模板定位", "二值化", "颗粒分析", "数据判定", "结果输出"],
    "表面划痕": ["图像源", "模板定位", "二值化", "颗粒分析", "数据判定", "结果输出"],
    "凹坑压痕": ["图像源", "模板定位", "二值化", "颗粒分析", "数据判定", "结果输出"],
    "异物脏污": ["图像源", "模板定位", "二值化", "颗粒分析", "数据判定", "结果输出"],
    "平面字符": ["图像源", "模板定位", "字符识别", "字符串比对", "结果输出"],
    "二维码": ["图像源", "模板定位", "条码识别", "字符串比对", "结果输出"],
    "高反光金属": ["图像源", "模板定位", "二值化", "颗粒分析", "数据判定", "结果输出"],
    "曲面圆柱": ["图像源", "模板定位", "直线查找", "圆查找", "数据判定", "结果输出"],
    "颜色判别": ["图像源", "模板定位", "颜色提取", "色差判定", "结果输出"],
}

ALIAS = {
    "图像源": "图像源（原图载入 / Image Source）",
    "模板定位": "模板定位（Template Matching）",
    "直线查找": "直线查找（抓边 / Caliper）",
    "圆查找": "圆查找（抓圆 / Circle Find）",
    "构造交点": "构造交点（Intersection）",
    "构造坐标系": "构造坐标系（Fixture / Coordinate）",
    "点距": "点距 / 点线距（Distance）",
    "二值化": "二值化（Threshold）",
    "颗粒分析": "颗粒分析（Blob / 连通域）",
    "字符识别": "字符识别（OCR）",
    "条码识别": "条码识别（Barcode / QR）",
    "字符串比对": "字符串比对（String Compare）",
    "颜色提取": "颜色提取（Color Extract）",
    "色差判定": "色差判定（Color Difference）",
    "数据判定": "数据判定（OK / NG）",
    "结果输出": "结果输出（TCP / Modbus / IO）",
}


def build_procedure(task: str, pixel_acc: float, accuracy_mm: float,
                    fov_w: float, fov_h: float, cam_w: int, cam_h: int,
                    gray_diff: float | None = None,
                    tol_mm: float | None = None,
                    plc_ip: str = "192.168.1.10", plc_port: int = 5000) -> list:
    """生成节点链与参数表。

    pixel_acc  : 像素精度 mm/px（来自相机选型）
    accuracy_mm: 最小可检特征 mm（来自图纸或用户输入）
    tol_mm     : 待判公差 mm（可选，用于点距上下限）
    gray_diff  : 图像诊断的特征/背景灰度差（可选）
    """
    chain = CHAINS.get(task, CHAINS["表面划痕"])
    steps = []

    def add(node, params=None, note=""):
        steps.append(Step(len(steps) + 1, ALIAS.get(node, node), params or [], note))

    # 最小缺陷在画面里占几个像素、面积约多少
    feat_px = accuracy_mm / pixel_acc if pixel_acc else 0
    area_px = max(9, round(feat_px * feat_px * 3))     # 3 倍余量，避免边缘抖动误判
    edge_thr = max(20, round((gray_diff or 120) / 4))
    tol_px = (tol_mm / pixel_acc) if tol_mm else None

    for node in chain:
        if node == "图像源":
            add(node, [
                ("分辨率", f"{cam_w}×{cam_h}", "相机选型结果"),
                ("曝光时间", "现场按亮度实测", "静止拍摄时曝光由光强决定，无拖影上限"),
                ("像素格式", ("Color8（彩色 Bayer/RGB）" if task_requires_color(task) else "Mono8（黑白）"),
                 "与相机选型一致"),
            ], f"视野 {fov_w:g}×{fov_h:g} mm；确认工件完整落在画面内，四周各留 10% 余量")

        elif node == "模板定位":
            add(node, [
                ("模板来源", "截取第一张良品图", "工件位置与角度每次不同，后续 ROI 要跟着它走"),
                ("匹配分数阈值", "0.7 ~ 0.8", "经验区间：太低会误匹配，太高良品也过不了"),
                ("角度范围", "±5°", "取决于上料方式；振动盘一般 ±3°~5°"),
                ("搜索区域", "全幅", "首次定位用全图，稳定后可缩小以提速"),
            ], "这一步的输出坐标是后面所有 ROI 的基准，配错会导致全线偏移；"
               "背光剪影场景用外轮廓做模板（形状匹配），不要用灰度模板")

        elif node == "直线查找":
            add(node, [
                ("边缘阈值", f"{edge_thr}", f"由图像灰度差 {gray_diff or '实测'} 折算，取约 1/4"),
                ("边缘极性", "暗→亮 或 亮→暗", "取决于基准边是轮廓还是台阶，配反了找不到边"),
                ("ROI 位置", "模板坐标 + 偏移", "先定位再抓边，不要写死绝对坐标"),
                ("拟合方式", "最小二乘", "抗单点噪声，比两点连线稳"),
            ])

        elif node == "圆查找":
            add(node, [
                ("边缘阈值", f"{edge_thr}", "同上，按灰度差折算"),
                ("半径范围", "按图纸名义值 ±20%", "缩小搜索范围避免抓到旁边特征"),
                ("拟合方式", "圆拟合（最小二乘）", "参与拟合点数越多越稳，但要排除弧段缺口"),
            ])

        elif node == "构造交点":
            add(node, [
                ("输入", "上两步的两条直线", "两线不能近乎平行，否则交点会飘"),
            ], "交点坐标是点距判定的测量起点")

        elif node == "点距":
            param = [("输入两点", "构造交点 + 模板基准点", "")]
            if tol_px:
                param.append(("判定上下限", f"名义值 ±{tol_px:.1f} px",
                              f"图纸公差 {tol_mm:g} mm ÷ 像素精度 {pixel_acc:.4f} mm/px"))
            else:
                param.append(("判定上下限", f"约 ±{feat_px:.1f} px",
                              f"最小可检特征 {accuracy_mm:g} mm ÷ 像素精度 {pixel_acc:.4f}"))
            add(node, param,
                "公差转像素这一步是全流程的关键换算；像素精度变了，上下限必须跟着改")

        elif node == "二值化":
            add(node, [
                ("阈值", "自动（Otsu）或手动", f"手动参考值：背景与特征之间取中，灰度差约 {gray_diff:.1f}" if gray_diff else "手动参考值：背景与特征之间取中"),
                ("极性", "特征为白", "决定颗粒分析统计的是缺陷还是背景，配反了会把背景当缺陷"),
            ], "先看直方图确认双峰，单峰说明光照不够，回上游改光；"
               "背光剪影是亮背景暗物体，极性要与前照明的亮场相反")

        elif node == "颗粒分析":
            add(node, [
                ("面积下限", f"{area_px} px", f"最小缺陷 {accuracy_mm:g} mm ≈ {feat_px:.1f} px，面积取 3 倍余量"),
                ("面积上限", "画面 20%", "防止把整块背景当成一个颗粒"),
                ("是否统计数量", "是", "多个小缺陷按数量判，不只看最大单体"),
            ], "面积下限定得太小会把噪声当缺陷，太大会漏掉小划痕")

        elif node == "字符识别":
            add(node, [("ROI", "模板定位输出 + 偏移", ""), ("字符高度", "≥ 30 px", "再小识别率会掉")])

        elif node == "条码识别":
            add(node, [("码制", "按图纸", ""), ("最小模块", "≥ 3 px", "低于 3 像素无法解码")])

        elif node == "字符串比对":
            add(node, [("比对方式", "完全匹配", "含空格与大小写，按图纸字符串逐字对")])

        elif node == "颜色提取":
            add(node, [("色彩空间", "HSV 或 RGB", "HSV 对光照变化更稳"), ("色差阈值", "按客户色卡", "")])

        elif node == "色差判定":
            add(node, [("判定方式", "ΔE 或灰度差", "ΔE ≤ 2 为目视无差别的常见口径")])

        elif node == "构造坐标系":
            add(node, [("原点", "模板定位输出", ""), ("X 轴", "由直线查找确定", "")],
                "坐标系一旦建立，后续所有坐标都相对它，工件移动不影响结果")

        elif node == "数据判定":
            add(node, [
                ("判据", "面积 ≥ 下限 判 NG" if task not in ("尺寸测量", "轮廓定位") else "点距超限判 NG",
                 "与上游节点输出绑定，不要另设一套阈值"),
                ("输出", "OK / NG 布尔值", "给结果输出节点用"),
            ])

        elif node == "结果输出":
            add(node, [
                ("协议", "TCP 客户端 / Modbus TCP", "按 PLC 侧支持的协议选"),
                ("目标地址", f"{plc_ip}:{plc_port}", "占位，按现场 PLC 实际地址填"),
                ("发送内容", "结果字（OK=1 / NG=0）+ 测量值", "先发结果字再发数值，PLC 好解析"),
            ], "触发方式与握手时序要和 PLC 一起定，单向发送容易丢帧")

    return steps


def to_markdown(task: str, steps: list, meta: dict) -> str:
    """导出成 Markdown，方便贴进工单或打印。"""
    lines = [
        f"# 检测流程作业指导书 · {task}",
        "",
        f"- 视野：{meta.get('fov')} mm",
        f"- 像素精度：{meta.get('pixel_acc')} mm/px",
        f"- 最小可检特征：{meta.get('accuracy')} mm",
        f"- 光源：{meta.get('light')}",
        "",
        "> 节点名用通用叫法，各视觉软件里名称略有差异，按功能对应即可。",
        "",
        "| 步 | 功能节点 | 参数 | 出处 |",
        "|---|---|---|---|",
    ]
    for s in steps:
        params = "<br>".join(f"{p[0]} = {p[1]}" for p in s.params) or "—"
        origins = "<br>".join(p[2] for p in s.params if p[2]) or "—"
        lines.append(f"| {s.no} | {s.node} | {params} | {origins} |")
    lines.append("")
    for s in steps:
        if s.note:
            lines.append(f"**第 {s.no} 步备注**：{s.note}")
            lines.append("")
    return "\n".join(lines)
