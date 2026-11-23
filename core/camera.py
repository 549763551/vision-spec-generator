"""相机选型计算。

公式与流程出处：行业通用选型方法第三章 选型总结
  第一步 定形态：面阵/线阵、黑白/彩色
  第二步 按精度与视野算最低分辨率与芯片尺寸
  第三步 定曝光方式：飞拍用全局、静止可用卷帘
  第四步 按速度核对帧率，再据此定镜头

用到的基础关系：
  精度(mm/pixel) = 视野 FOV(mm) / 分辨率(pixel)
  曝光时间上限  t <= 精度 / 运动速度
  行频          = 运动速度 / 精度
"""

from dataclasses import dataclass, field
import math


# 常见工业相机档位：(标称百万像素, 宽, 高, 靶面代号, 靶面宽mm, 靶面高mm)
# 数值为行业常见规格，非某一厂商选型手册；答辩时以实际样本为准。
SENSOR_TABLE = [
    (0.3,  640,  480,  '1/4"',   3.60,  2.70),
    (0.5,  800,  600,  '1/3.6"', 4.80,  3.60),
    (1.3,  1280, 1024, '1/2.5"', 5.70,  4.28),
    (2.0,  1600, 1200, '1/1.8"', 7.20,  5.40),
    (3.0,  2048, 1536, '1/1.8"', 7.07,  5.30),
    (5.0,  2448, 2048, '2/3"',   8.45,  7.07),
    (6.3,  3072, 2048, '1/1.8"', 7.20,  4.80),
    (12.0, 4096, 3000, '1/1.1"', 14.13, 10.35),
    (20.0, 5472, 3648, '1"',     13.10, 8.80),
    (25.0, 5120, 5120, '1.1"',   12.30, 12.30),
]


@dataclass
class CameraSpec:
    """相机选型结果。steps 保存完整计算过程，可直接渲染进方案书。"""
    megapixel: float
    width_px: int
    height_px: int
    sensor_name: str
    sensor_w: float
    sensor_h: float
    pixel_um: float
    pixel_accuracy_mm: float
    res_for_accuracy: tuple
    res_for_defect: tuple
    exposure_max_us: float | None
    fps_min: float | None
    shutter: str
    color_mode: str
    interface: str = ""
    pixel_depth: str = ""
    mount: str = ""
    scan: str = "area"                 # area / line
    line_rate_hz: float | None = None  # 线阵行频
    data_rate_mbps: float | None = None
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


# 线阵档位：(横向像素数, 像元 μm, 名称)
LINE_SENSOR_TABLE = [
    (2048,  7.0, "2K 线阵（7 μm）"),
    (4096,  7.0, "4K 线阵（7 μm）"),
    (8192,  7.0, "8K 线阵（7 μm）"),
    (16384, 3.5, "16K 线阵（3.5 μm）"),
]


def _ceil_div(a: float, b: float) -> int:
    return int(math.ceil(a / b))


def select_camera(fov_w: float, fov_h: float, accuracy: float,
                  moving: bool = False, speed: float = 0.0,
                  need_color: bool = False, feature_px: int = 3,
                  fov_margin: float = 0.0, scan: str = "area") -> CameraSpec:
    """按通行做法的选型流程推算相机。

    参数
      fov_w, fov_h : 需要拍到的实际视野，单位 mm
      accuracy     : 需要分辨的最小尺寸，单位 mm（即"精度要求 0.01mm"里的 0.01）
      moving       : 是否运动拍摄（飞拍）
      speed        : 运动速度 mm/s，moving=True 时使用
      need_color   : 是否必须保留颜色信息
      feature_px   : 一个缺陷至少要占几个像素（通行做法取 3~4，默认 3）
      fov_margin   : 视野余量，0.2 表示每边放大 20%（通行做法练习把 10x8 放大到 12x10）
    """
    if scan == "line":
        return select_line_camera(fov_w=fov_w, accuracy=accuracy, speed=speed,
                                  feature_px=feature_px, fov_margin=fov_margin,
                                  need_color=need_color)

    steps = []
    warnings = []

    # --- 0. 视野余量 ---
    fov_w_eff = fov_w * (1 + fov_margin)
    fov_h_eff = fov_h * (1 + fov_margin)
    if fov_margin:
        steps.append(
            f"视野留余量 {fov_margin:.0%}：{fov_w:g}×{fov_h:g} → "
            f"{fov_w_eff:.1f}×{fov_h_eff:.1f} mm"
        )
    else:
        steps.append(f"有效视野：{fov_w_eff:g}×{fov_h_eff:g} mm（已含余量）")

    # --- 1. 精度级最低分辨率（通行做法：精度 = 视野 / 分辨率）---
    w_acc = _ceil_div(fov_w_eff, accuracy)
    h_acc = _ceil_div(fov_h_eff, accuracy)
    steps.append(
        f"按精度反推最低分辨率：{fov_w_eff:.1f}÷{accuracy:g} = {w_acc} px，"
        f"{fov_h_eff:.1f}÷{accuracy:g} = {h_acc} px "
        f"→ {w_acc}×{h_acc} ≈ {w_acc * h_acc / 1e6:.2f} MP"
    )

    # --- 2. 缺陷可检分辨率（通行做法练习：一个缺陷要占 3~4 个像素）---
    w_feat = w_acc * feature_px
    h_feat = h_acc * feature_px
    steps.append(
        f"按缺陷占 {feature_px} px 放大：{w_acc}×{feature_px} = {w_feat} px，"
        f"{h_acc}×{feature_px} = {h_feat} px "
        f"→ {w_feat}×{h_feat} ≈ {w_feat * h_feat / 1e6:.2f} MP"
    )

    # --- 3. 选档位：第一个宽高都不小于需求的档位 ---
    chosen = None
    for mp, w, h, name, sw, sh in SENSOR_TABLE:
        if w >= w_feat and h >= h_feat:
            chosen = (mp, w, h, name, sw, sh)
            break
    if chosen is None:
        mp, w, h, name, sw, sh = SENSOR_TABLE[-1]
        chosen = (mp, w, h, name, sw, sh)
        warnings.append(
            f"需求 {w_feat}×{h_feat} 超过 25MP 档位，需拼接或改线阵，当前按最高档给出"
        )
    mp, w, h, name, sw, sh = chosen
    steps.append(
        f"取满足需求的最小档位：{mp:g} MP（{w}×{h}，靶面 {name} {sw}×{sh} mm）"
    )

    # 档位余量提醒：刚好卡在边界时，实际装配公差会吃掉余量
    cover_ratio = min(w / w_feat, h / h_feat)
    if cover_ratio < 1.15:
        warnings.append(
            f"所选档位对需求的余量仅 {cover_ratio:.2f}×，接近边界；"
            f"现场装配偏差可能导致视野不够，建议上调一档"
        )

    # --- 4. 实际像素精度（这才是最终交付给算法的数）---
    pixel_accuracy = fov_w_eff / w
    pixel_um = sw * 1000 / w
    steps.append(
        f"实际像素精度 = {fov_w_eff:.1f}÷{w} = {pixel_accuracy:.4f} mm/px"
        f"（像元 {pixel_um:.1f} μm）"
    )
    if pixel_accuracy > accuracy:
        warnings.append(
            f"实际精度 {pixel_accuracy:.4f} mm/px 已优于要求 {accuracy:g} mm，达标"
        )

    # --- 5. 曝光方式（通行做法：飞拍用全局，静止可用卷帘）---
    shutter = "全局曝光（Global）" if moving else "卷帘曝光可用（建议全局）"
    steps.append(f"曝光方式：{'运动拍摄 → 必须全局曝光，否则拖影' if moving else '静止拍摄 → 卷帘可用，成本更低'}")

    # --- 6. 曝光时间上限与帧率（通行做法：t ≤ 精度/速度；行频 = 速度/精度）---
    exposure_max_us = None
    fps_min = None
    if moving and speed > 0:
        t_max = accuracy / speed          # 秒
        exposure_max_us = t_max * 1e6
        fps_min = speed / fov_h_eff
        steps.append(
            f"曝光时间上限 = 精度÷速度 = {accuracy:g}÷{speed:g} = {t_max * 1e6:.1f} μs"
        )
        steps.append(
            f"帧率下限 = 速度÷视野高 = {speed:g}÷{fov_h_eff:.1f} = {fps_min:.2f} fps"
            f"（按 1 帧/视野计算，工程上建议取 2~3 倍）"
        )
        if exposure_max_us < 100:
            warnings.append(
                f"曝光时间 {exposure_max_us:.0f} μs 已进入常亮光源难以补亮的区间，"
                f"需配频闪/爆闪控制器"
            )

    # --- 7. 黑白 / 彩色 ---
    color_mode = "彩色" if need_color else "黑白"
    steps.append(
        f"色彩：{'需要颜色判别 → 彩色相机' if need_color else '仅判尺寸/缺陷 → 黑白，灵敏度更高、同价位分辨率更好'}"
    )

    # --- 8. 数据接口 / 像素深度 / 镜头接口（带宽与距离的权衡）---
    if fps_min and fps_min > 60:
        interface = "Camera Link 或 CoaXPress（带宽 6.8G 以上，可走 10~40m）"
    elif mp > 20:
        interface = "Camera Link（大靶面无压缩高数据量）"
    elif fps_min and fps_min > 30:
        interface = "USB3（带宽约 5G，但线长限 3 米）"
    else:
        interface = "GigE（带宽 1G，可走 100 米，工业现场默认）"
    steps.append(f"数据接口：{interface}")
    steps.append(
        "像素深度：8 bit（256 级）够用；需要更细层次可上 10 bit（1024 级），"
        "代价是数据量增加、传输与处理压力变大"
    )
    mount = "C 口（法兰距 17.56mm，最常见）" if mp <= 25 else "F 口 / M42（超高像素或线阵用大口径）"
    steps.append(f"镜头接口：{mount}；C 口镜头装不上 CS 口机身，CS 口镜头可装 C 口机身")

    return CameraSpec(
        megapixel=mp, width_px=w, height_px=h,
        interface=interface, pixel_depth="8 bit（可选 10 bit）", mount=mount,
        sensor_name=name, sensor_w=sw, sensor_h=sh, pixel_um=pixel_um,
        pixel_accuracy_mm=pixel_accuracy,
        res_for_accuracy=(w_acc, h_acc),
        res_for_defect=(w_feat, h_feat),
        exposure_max_us=exposure_max_us,
        fps_min=fps_min,
        shutter=shutter, color_mode=color_mode,
        steps=steps, warnings=warnings,
    )


def select_line_camera(fov_w: float, accuracy: float, speed: float = 0.0,
                       feature_px: int = 3, fov_margin: float = 0.0,
                       need_color: bool = False) -> CameraSpec:
    """线阵相机选型。

    与面阵的区别：线阵只有一个方向的像素（横向），另一维靠运动扫出来，
    所以视野高度不参与分辨率计算，改由行频决定纵向采样密度。
    """
    steps = []
    warnings = []

    fov_w_eff = fov_w * (1 + fov_margin)
    if fov_margin:
        steps.append(f"扫描宽度留余量 {fov_margin:.0%}：{fov_w:g} → {fov_w_eff:.1f} mm")
    else:
        steps.append(f"扫描宽度：{fov_w_eff:g} mm（已含余量）")

    n_acc = _ceil_div(fov_w_eff, accuracy)
    steps.append(
        f"按精度反推横向像素：{fov_w_eff:.1f}÷{accuracy:g} = {n_acc} px"
        f"（线阵只有横向像素，纵向由行频生成）"
    )
    n_feat = n_acc * feature_px
    steps.append(f"按缺陷占 {feature_px} px 放大：{n_acc}×{feature_px} = {n_feat} px")

    chosen = None
    for npx, um, name in LINE_SENSOR_TABLE:
        if npx >= n_feat:
            chosen = (npx, um, name)
            break
    if chosen is None:
        chosen = LINE_SENSOR_TABLE[-1]
        warnings.append(f"需求 {n_feat} px 超过 16K 单芯片，需双相机拼接或分两次扫描")
    npx, um, name = chosen
    steps.append(f"取满足需求的最小档位：{name}（{npx} px）")

    pixel_accuracy = fov_w_eff / npx
    sensor_w = npx * um / 1000.0
    sensor_h = um / 1000.0
    steps.append(
        f"实际横向像素精度 = {fov_w_eff:.1f}÷{npx} = {pixel_accuracy:.4f} mm/px"
        f"（像元 {um:g} μm，像面宽 {sensor_w:.1f} mm）"
    )

    line_rate = None
    data_rate = None
    exposure_max_us = None
    if speed > 0:
        line_rate = speed / pixel_accuracy
        data_rate = npx * line_rate / 1e6
        exposure_max_us = 1e6 / line_rate
        steps.append(
            f"行频 = 速度÷像素精度 = {speed:g}÷{pixel_accuracy:.4f} = {line_rate:.0f} Hz"
            f"（纵向像素与横向等宽，才不会拉长变形）"
        )
        steps.append(
            f"单行曝光上限 = 1÷行频 = {exposure_max_us:.1f} μs，超过就会拖影"
        )
        steps.append(
            f"数据率 = {npx} px × {line_rate:.0f} Hz × 1 Byte ≈ {data_rate:.0f} MB/s"
        )
    else:
        warnings.append("线阵必须配合运动：未给速度就算不出行频，也无法判断曝光与带宽")

    if data_rate and data_rate > 600:
        interface = "CoaXPress 或 Camera Link HS（25G 级，必须）"
    elif data_rate and data_rate > 200:
        interface = "Camera Link（双/四通道）"
    else:
        interface = "GigE Vision（低行频时够用）"
    steps.append(f"数据接口：{interface}")

    mount = "M42 / F 口（线阵像面宽，C 口覆盖不了）"
    steps.append(f"镜头接口：{mount}")

    return CameraSpec(
        megapixel=round(npx / 1e6, 4),
        width_px=npx, height_px=1,
        sensor_name=name, sensor_w=round(sensor_w, 3), sensor_h=round(sensor_h, 4),
        pixel_um=um, pixel_accuracy_mm=pixel_accuracy,
        res_for_accuracy=(n_acc, 1), res_for_defect=(n_feat, 1),
        exposure_max_us=exposure_max_us, fps_min=line_rate,
        shutter="逐行曝光（与运动同步）",
        color_mode="彩色" if need_color else "黑白",
        interface=interface, pixel_depth="8 bit（可选 10 bit）", mount=mount,
        scan="line", line_rate_hz=line_rate, data_rate_mbps=data_rate,
        steps=steps, warnings=warnings,
    )
