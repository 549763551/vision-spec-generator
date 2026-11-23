"""镜头选型计算。

核心公式出处：行业通用选型方法PART 01 焦距的计算
  把镜头简化为两个顶点相接的相似三角形：
      f / WD = Sensor / FOV      （f≈像距，WD≈物距）
  三个量已知即可求第四个；两边必须取同一方向——长边配长边、短边配短边。
  页面红字：当视野长宽比 < 芯片长宽比时，必须改用短边计算，
            否则长边方向会"凸出来一块"拍不到。

其他依据：
  视场角  —— PART 01 视场角：焦距越短视场角越大
  靶面    —— PART 01 靶面尺寸：镜头靶面必须 ≥ 相机靶面
  景深    —— PART 01 景深：焦距越短、光圈越小，景深越大
  远心    —— PART 03：精密测量才用远心，表面缺陷/有无判断用 FA 即可
"""

from dataclasses import dataclass, field
import math


# 通行做法列出的常见焦距档位（定焦镜头无法连续调到任意值）
FOCAL_STEPS = [6, 8, 12, 16, 25, 35, 50, 75]


@dataclass
class LensSpec:
    f_calc: float
    f_recommend: float
    f_alt: float | None
    wd_at_recommend: float
    wd_at_alt: float | None
    fov_angle_deg: float
    magnification: float
    dof_estimate_mm: float
    use_side: str
    need_telecentric: bool
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def select_lens(sensor_w: float, sensor_h: float, fov_w: float, fov_h: float,
                wd: float, pixel_um: float = 3.45, f_number: float = 2.8,
                need_precision_measure: bool = False,
                height_variation: float = 0.0) -> LensSpec:
    """按相似三角形推算焦距，并给出两档可选焦距与对应工作距离。

    参数
      sensor_w, sensor_h : 相机靶面尺寸 mm（来自相机选型结果）
      fov_w, fov_h       : 视野 mm
      wd                 : 期望工作距离 mm（现场可用空间，通行做法算例 130）
      pixel_um           : 像元尺寸 μm（用于估算景深）
      f_number           : 光圈 F 数，通行做法图中镜头为 f:2.8
      need_precision_measure : 是否为精密尺寸测量（决定是否建议远心）
      height_variation   : 被测物沿光轴的高度变化 mm（判定景深是否够）
    """
    steps = []
    warnings = []

    # --- 1. 判定用长边还是短边（通行做法红字）---
    fov_ratio = fov_w / fov_h
    sensor_ratio = sensor_w / sensor_h
    if fov_ratio >= sensor_ratio:
        use_w, use_h = fov_w, sensor_w
        side = "长边"
        note = f"视野长宽比 {fov_ratio:.3f} ≥ 芯片长宽比 {sensor_ratio:.3f}，按长边计算"
    else:
        use_w, use_h = fov_h, sensor_h
        side = "短边"
        note = (f"视野长宽比 {fov_ratio:.3f} < 芯片长宽比 {sensor_ratio:.3f}，"
                f"改用短边计算，否则长边方向拍不全")
    steps.append(note)

    # --- 2. 求焦距 f = WD × Sensor / FOV ---
    f_calc = wd * use_h / use_w
    steps.append(
        f"f = WD × Sensor / FOV = {wd:g} × {use_h:g} ÷ {use_w:g} = {f_calc:.2f} mm"
    )

    # --- 3. 落到可用档位（定焦镜头只能选标准值）---
    above = [f for f in FOCAL_STEPS if f >= f_calc]
    below = [f for f in FOCAL_STEPS if f <= f_calc]
    f_rec = above[0] if above else FOCAL_STEPS[-1]
    f_alt = below[-1] if below else None
    if f_rec != f_calc:
        steps.append(f"定焦镜头无法连续可调，向上取最近档位 {f_rec}mm（工作距离会变远）")
    if f_alt:
        steps.append(f"另一档可选 {f_alt}mm（工作距离会变近，机身要装得更低）")

    # 超出常用档位范围：这是"大靶面相机配小视野"的典型冲突
    if f_calc > FOCAL_STEPS[-1]:
        warnings.append(
            f"计算焦距 {f_calc:.1f}mm 超出常用档位上限 {FOCAL_STEPS[-1]}mm——"
            f"大靶面相机配小视野时必然出现。三条出路：① 缩短工作距离；"
            f"② 换小靶面相机（如 2/3\"）；③ 用 1× 远心镜头（视野与工作距离固定）"
        )
    elif f_calc < FOCAL_STEPS[0]:
        warnings.append(
            f"计算焦距 {f_calc:.1f}mm 低于最短档位 {FOCAL_STEPS[0]}mm，"
            f"视野过大或工作距离过近，需确认安装空间"
        )

    # --- 4. 用选定焦距反算真实工作距离 ---
    wd_rec = f_rec * use_w / use_h
    steps.append(f"{f_rec}mm 对应工作距离 WD = {f_rec} × {use_w:g} ÷ {use_h:g} = {wd_rec:.1f} mm")
    wd_alt = None
    if f_alt:
        wd_alt = f_alt * use_w / use_h
        steps.append(f"{f_alt}mm 对应工作距离 WD = {wd_alt:.1f} mm")
        if wd_alt < wd_rec:
            steps.append(
                f"选 {f_alt}mm 相机装得更低（{wd_alt:.0f}mm），"
                f"选 {f_rec}mm 装得更高（{wd_rec:.0f}mm）——按现场限高与干涉决定"
            )

    # --- 5. 视场角与放大倍率 ---
    fov_angle = 2 * math.degrees(math.atan(use_h / (2 * f_rec)))
    mag = use_h / use_w
    steps.append(f"视场角 = 2×atan({use_h:g}÷(2×{f_rec})) = {fov_angle:.1f}°（焦距越短视场角越大）")
    steps.append(f"放大倍率 β = Sensor÷FOV = {use_h:g}÷{use_w:g} = {mag:.3f}×")

    # --- 6. 景深估算（近摄近似，非厂商实测值）---
    c = 2 * pixel_um / 1000.0          # 容许弥散圆，取 2 倍像元
    dof = 2 * f_number * c * (1 + mag) / (mag ** 2)
    steps.append(
        f"景深估算 = 2·N·c·(1+β)/β² = 2×{f_number}×{c:.4f}×{1 + mag:.3f}÷{mag ** 2:.4f} "
        f"= {dof:.3f} mm（N 为光圈 F 数，c 取 2 倍像元；估算值，以实测为准）"
    )
    if height_variation and height_variation > dof:
        warnings.append(
            f"被测物高度变化 {height_variation:g}mm 已超过景深 {dof:.3f}mm，"
            f"需要缩小光圈（增大 F 数）或改用远心镜头"
        )

    # --- 7. 是否需要远心（通行做法的选型判断）---
    need_tele = need_precision_measure
    if need_tele:
        steps.append(
            "检测目的为精密尺寸测量 → 建议远心镜头："
            "普通镜头拍照高度变化 0.2mm，测量值就从 5.008 变到 5.014"
        )
    else:
        steps.append("检测目的为表面缺陷/有无判断 → 畸变小的 FA 镜头即可，无需远心")

    # --- 8. 靶面色差提醒 ---
    if mag > 0.5:
        warnings.append(f"放大倍率 {mag:.2f}× 偏大，需确认镜头靶面 ≥ 相机靶面（{sensor_w}×{sensor_h}mm）")

    return LensSpec(
        f_calc=f_calc, f_recommend=f_rec, f_alt=f_alt,
        wd_at_recommend=wd_rec, wd_at_alt=wd_alt,
        fov_angle_deg=fov_angle, magnification=mag,
        dof_estimate_mm=dof, use_side=side,
        need_telecentric=need_tele,
        steps=steps, warnings=warnings,
    )
