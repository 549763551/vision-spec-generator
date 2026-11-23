"""光源控制器选型。

依据：行业通用选型方法CST 控制器培训
   分类与命名：APS 模拟 / DPS 数字 / MDPS 迷你数字 / SPS 频闪 /
             BPS 爆闪 / CPL 恒流 / TPS 多路时序
             型号格式 CST-APS 24 60 B-4TD：24=电压V，60=功率W，
             版本 A 仅旋钮 / B 数显+串口 / C 数显+串口+网口，
             4=通道数（是线数，不是光源个数），T=触发，D=导轨安装
   选型小结：串口控制只有 DPS 与 SPS 有；增亮功能只有 SPS（BPS 同理）有
   选型三步：定光源 → 定控制方式（要不要程序控制）→ 定是否飞拍/要增亮
"""

from dataclasses import dataclass, field


@dataclass
class ControllerSpec:
    series: str
    series_full: str
    model_string: str
    version: str
    voltage: int
    power_w: int
    channels: int
    has_serial: bool
    has_ethernet: bool
    has_boost: bool
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def select_controller(light_channels: int, channel_power_w: float,
                      need_program_control: bool = False,
                      need_boost: bool = False,
                      exposure_max_us: float | None = None,
                      need_time_sequence: bool = False,
                      need_stable_brightness: bool = False,
                      voltage: int = 24) -> ControllerSpec:
    """按通行做法三步法选控制器。

    参数
      light_channels      : 需要驱动的光源线数（注意：是线数，不是光源个数）
      channel_power_w     : 单路线功率 W
      need_program_control: 是否需要电脑程序控制亮度（要串口/网口）
      need_boost          : 是否需要瞬时增亮
      exposure_max_us     : 相机算出的曝光时间上限 μs
      need_time_sequence  : 是否需要多路分时/分区域点亮
      need_stable_brightness : 是否需要长期亮度稳定（大功率恒流）
    """
    steps = []
    warnings = []

    total_power = light_channels * channel_power_w

    # --- 第一步：先看是不是需要分时/多角度合成 ---
    if need_time_sequence:
        series, full = "TPS", "多路时序光源控制器"
        steps.append("需要多路分时/分区域照明 → TPS：可 T1 用同轴、T2 用线光，分时拍两个角度再合成")
        has_boost = False
    # --- 第二步：增亮需求优先，频闪/爆闪才有增亮 ---
    elif need_boost or (exposure_max_us is not None and exposure_max_us < 200):
        if exposure_max_us is not None and exposure_max_us < 50:
            series, full = "BPS", "爆闪控制器"
            steps.append(
                f"曝光上限仅 {exposure_max_us:.0f} μs → BPS 爆闪：比频闪更极端的瞬时大电流点亮"
            )
        else:
            series, full = "SPS", "频闪控制器"
            steps.append(
                f"曝光上限 {exposure_max_us:.0f} μs 已低于常亮可补亮区间 → SPS 频闪，"
                f"极短脉宽+大电流换取瞬时增亮"
            )
        has_boost = True
    # --- 第三步：数字 / 恒流 / 模拟 ---
    elif need_stable_brightness or total_power >= 120:
        series, full = "CPL", "恒流控制器"
        steps.append(
            f"总功率 {total_power:.0f}W 偏大或要求亮度长期稳定 → CPL 恒流，锁住输出电流"
        )
        has_boost = False
    elif need_program_control:
        series, full = "DPS", "数字控制器"
        steps.append("需要程序控制亮度 → DPS 数字控制器，按键/串口/网口控制")
        has_boost = False
    else:
        series, full = "APS", "模拟控制器"
        steps.append("只需面板旋钮调光、不接入程序 → APS 模拟控制器，成本最低")
        has_boost = False

    # --- 版本与通讯口（通行做法：B=串口，C=串口+网口，A=仅旋钮）---
    has_serial = series in ("DPS", "SPS")
    has_ethernet = False
    if need_program_control:
        if series in ("DPS", "SPS"):
            version = "C"
            has_ethernet = True
            steps.append("需要程序控制 → 选 C 版：数显 + 串口 + 网口（B 版只有串口）")
        else:
            version = "C" if series == "TPS" else "-"
            steps.append(f"{series} 本身无串口控制能力，若必须程序控制需改选 DPS 或 SPS")
            warnings.append(f"{full}不支持串口/网口控制，与「需要程序控制」冲突")
            has_serial = False
    else:
        version = "A"
        steps.append("不需要程序控制 → A 版仅旋钮，够用且便宜")

    # --- 功率与通道 ---
    power_w = int((total_power * 1.3 + 9) // 10 * 10)   # 留 30% 余量并向上取整到 10W
    steps.append(
        f"通道数 = {light_channels} 路（线数，不是光源个数，一个光源可能占多路）"
    )
    steps.append(
        f"功率 = {light_channels}×{channel_power_w:g}×1.3 余量 = {power_w}W，电压 {voltage}V"
    )

    model = f"CST-{series} {voltage} {power_w} {version}-{light_channels}TD"
    steps.append(f"按命名规则推导型号：{model}（采购前需核对实际样本与库存）")

    if series == "APS" and need_program_control:
        warnings.append("模拟控制器无法走数字通讯，上位机读不到当前亮度值")

    return ControllerSpec(
        series=series, series_full=full, model_string=model, version=version,
        voltage=voltage, power_w=power_w, channels=light_channels,
        has_serial=has_serial, has_ethernet=has_ethernet, has_boost=has_boost,
        steps=steps, warnings=warnings,
    )
