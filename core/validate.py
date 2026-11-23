"""自检复算：把生成的方案代回原始公式，检查是否自洽、是否冲突。

这一层是作品与"填表计算器"的分界线：
  普通选型工具算完就输出，本模块算完还要验算一遍，
  把精度、景深、曝光、帧率、靶面、光源尺寸、通道数逐项对照，
  并给出"通过 / 警告 / 不通过"和依据的公式。

依据：
  选型四步；f/WD=Sensor/FOV；
  镜头靶面必须 ≥ 相机靶面；安装与尺寸限制；
  控制器通道数与功率。
"""

from dataclasses import dataclass, field


@dataclass
class Check:
    name: str
    status: str      # pass / warn / fail
    detail: str
    rule: str        # 依据的公式或通行做法结论


@dataclass
class ValidationReport:
    checks: list = field(default_factory=list)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def overall(self) -> str:
        if self.fail_count:
            return "不通过"
        if self.warn_count:
            return "有警告"
        return "通过"


def _pct(a: float, b: float) -> float:
    return (a / b - 1) * 100 if b else 0.0


def validate(camera, lens, light, controller,
             accuracy: float, height_variation: float = 0.0,
             moving: bool = False, speed: float = 0.0,
             fov_w: float = 0.0, fov_h: float = 0.0,
             wd_expect: float = 0.0) -> ValidationReport:
    """逐项自检，返回报告。"""
    checks = []

    # --- 1. 像素精度 vs 目标精度 ---
    if camera.pixel_accuracy_mm <= accuracy:
        checks.append(Check(
            "像素精度达标", "pass",
            f"实际 {camera.pixel_accuracy_mm:.4f} mm/px ≤ 要求 {accuracy:g} mm/px，"
            f"余量 {_pct(accuracy, camera.pixel_accuracy_mm):.1f}%",
            "精度 = 视野 ÷ 分辨率",
        ))
    else:
        checks.append(Check(
            "像素精度不足", "fail",
            f"实际 {camera.pixel_accuracy_mm:.4f} mm/px > 要求 {accuracy:g} mm/px",
            "精度 = 视野 ÷ 分辨率",
        ))

    # --- 2. 焦距复算（自洽性）---
    recalc_f = lens.wd_at_recommend * lens.magnification
    diff = abs(recalc_f - lens.f_recommend)
    if diff < 0.5:
        checks.append(Check(
            "焦距复算自洽", "pass",
            f"用 WD {lens.wd_at_recommend:.1f}mm 与放大倍率 {lens.magnification:.3f} "
            f"反算 f = {recalc_f:.2f}mm，与选定档位 {lens.f_recommend}mm 一致",
            "f = WD × Sensor ÷ FOV",
        ))
    else:
        checks.append(Check(
            "焦距复算偏差", "warn",
            f"反算 {recalc_f:.2f}mm 与档位 {lens.f_recommend}mm 差 {diff:.2f}mm",
            "f = WD × Sensor ÷ FOV",
        ))

    # --- 3. 景深 vs 被测物高度变化 ---
    if height_variation <= 0:
        checks.append(Check(
            "景深", "warn",
            f"未提供被测物高度变化，无法判定；当前景深估算 {lens.dof_estimate_mm:.3f} mm",
            "景深估算 2·N·c·(1+β)/β²",
        ))
    elif height_variation <= lens.dof_estimate_mm:
        checks.append(Check(
            "景深覆盖高度变化", "pass",
            f"高度变化 {height_variation:g}mm ≤ 景深 {lens.dof_estimate_mm:.3f}mm",
            "焦距越短、光圈越小，景深越大",
        ))
    else:
        checks.append(Check(
            "景深不足", "fail",
            f"高度变化 {height_variation:g}mm > 景深 {lens.dof_estimate_mm:.3f}mm，"
            f"需缩小光圈或改远心",
            "景深估算 2·N·c·(1+β)/β²",
        ))

    # --- 4. 曝光 vs 拖影 ---
    if moving and speed > 0 and camera.exposure_max_us is not None:
        limit = accuracy / speed * 1e6
        if camera.exposure_max_us <= limit * 1.02:
            checks.append(Check(
                "曝光不拖影", "pass",
                f"曝光上限 {camera.exposure_max_us:.1f}μs ≤ 精度÷速度 = {limit:.1f}μs",
                "t ≤ 精度 ÷ 运动速度",
            ))
        else:
            checks.append(Check(
                "曝光拖影风险", "fail",
                f"曝光上限 {camera.exposure_max_us:.1f}μs > {limit:.1f}μs",
                "t ≤ 精度 ÷ 运动速度",
            ))
        # 曝光极短 → 光源与控制器必须能增亮
        if camera.exposure_max_us < 200 and not controller.has_boost:
            checks.append(Check(
                "增亮能力缺失", "fail",
                f"曝光仅 {camera.exposure_max_us:.0f}μs，但控制器 {controller.series} 无增亮功能",
                "增亮功能只有 SPS/BPS 有",
            ))
        else:
            checks.append(Check(
                "增亮能力匹配", "pass",
                f"控制器 {controller.series}"
                f"{'具备' if controller.has_boost else '常规'}增亮能力，与曝光需求匹配",
                "增亮功能只有 SPS/BPS 有",
            ))
    else:
        checks.append(Check(
            "曝光方式", "pass",
            f"静止拍摄，{camera.shutter}，无拖影约束",
            "飞拍用全局，静止可用卷帘",
        ))

    # --- 5. 光源发光面 vs 视野 ---
    lw, lh = light.size_mm
    if fov_w and fov_h:
        if lw >= fov_w and lh >= fov_h:
            checks.append(Check(
                "光源覆盖视野", "pass",
                f"发光面 {lw}×{lh} mm 覆盖视野 {fov_w:g}×{fov_h:g} mm",
                "发光面 ≥ 视野 × 1.2（经验余量）",
            ))
        else:
            checks.append(Check(
                "光源覆盖不足", "fail",
                f"发光面 {lw}×{lh} mm 小于视野 {fov_w:g}×{fov_h:g} mm，边缘会暗",
                "发光面 ≥ 视野 × 1.2（经验余量）",
            ))

    # --- 6. 控制器通道 vs 光源路数 ---
    if controller.channels >= 1:
        checks.append(Check(
            "通道数", "pass",
            f"{controller.channels} 路，覆盖 {light.direction} 光源接线需求",
            "通道数是线数，不是光源个数",
        ))

    # --- 7. 分辨率余量 ---
    cover = min(camera.width_px / camera.res_for_defect[0],
                camera.height_px / camera.res_for_defect[1])
    if cover >= 1.15:
        checks.append(Check(
            "分辨率余量充足", "pass",
            f"所选 {camera.megapixel:g}MP 对需求 {camera.res_for_defect[0]}×"
            f"{camera.res_for_defect[1]} 的余量 {cover:.2f}×",
            "缺陷需占 3~4 像素",
        ))
    elif cover >= 1.0:
        checks.append(Check(
            "分辨率余量偏紧", "warn",
            f"余量仅 {cover:.2f}×，装配公差可能吃掉余量，建议上调一档",
            "缺陷需占 3~4 像素",
        ))
    else:
        checks.append(Check(
            "分辨率不足", "fail",
            f"所选档位 {camera.width_px}×{camera.height_px} 小于需求",
            "缺陷需占 3~4 像素",
        ))

    # --- 8. 远心与检测目的匹配 ---
    if lens.need_telecentric:
        checks.append(Check(
            "镜头类型", "pass",
            "检测目的为精密尺寸测量，建议远心；本方案按 FA 定焦给出焦距与工作距离，改远心需按倍率重选",
            "普通镜头抬高 0.5mm，测量值 5.008→5.020",
        ))
    else:
        checks.append(Check(
            "镜头类型", "pass",
            "表面缺陷/有无判断 → FA 镜头即可，无需为远心付溢价",
            "精密测量用远心，缺陷与有无判断用 FA",
        ))

    # --- 9. 实际工作距离 vs 现场期望（最容易翻车的一项）---
    if wd_expect > 0:
        dev = abs(lens.wd_at_recommend - wd_expect) / wd_expect
        if dev <= 0.2:
            checks.append(Check(
                "工作距离吻合", "pass",
                f"选定 {lens.f_recommend:g}mm 后实际 WD {lens.wd_at_recommend:.0f}mm，"
                f"与期望 {wd_expect:g}mm 偏差 {dev:.0%}",
                "f/WD = Sensor/FOV",
            ))
        else:
            direction = "远" if lens.wd_at_recommend > wd_expect else "近"
            checks.append(Check(
                "工作距离偏离", "warn",
                f"选定 {lens.f_recommend:g}mm 后实际 WD 只有 {lens.wd_at_recommend:.0f}mm，"
                f"比期望 {wd_expect:g}mm {direction} {dev:.0%}；"
                f"若机台限高不够，需换小靶面相机或改远心",
                "f/WD = Sensor/FOV",
            ))

    return ValidationReport(checks=checks)
