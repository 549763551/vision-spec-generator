"""修复方向建议：对自检的警告 / 不通过项，反解出"该调哪个参数、调到多少"。

为什么要有这一层：自检复算发现问题后，旧流程停在"景深不足""工作距离偏离"，
用户仍要回样本册重新手算一遍才知道怎么改。本模块把修法也做成可复算的：
每条建议都来自 core.camera / core.lens 同一批公式的逆运算，不是"建议人工确认"。

反解依据（与前向计算同源，可逐条核对）：
  视野上限   = 分辨率 × 精度            （精度 = 视野 ÷ 分辨率 的逆）
  光圈反解   N = 需求景深 × β² ÷ (2·c·(1+β))   （景深公式的逆，c 取 2 倍像元）
  速度上限   = 精度 ÷ 曝光              （t ≤ 精度 ÷ 速度 的逆）
  工作距离   = f ÷ β                    （f / WD = Sensor / FOV 的逆）
  焦距档位反选 = 限高 WD × β，落回 FOCAL_STEPS 最近档
"""

from core.camera import SENSOR_TABLE
from core.lens import FOCAL_STEPS


def attach_remedies(report, camera, lens, light, controller,
                    accuracy: float, height_variation: float = 0.0,
                    moving: bool = False, speed: float = 0.0,
                    fov_w: float = 0.0, fov_h: float = 0.0,
                    wd_expect: float = 0.0):
    """对报告中每条非 pass 的检查项回填修复方向（原地修改 Check.remedies）。

    fov_w / fov_h 应传与自检一致的视野——多拍方案传单幅视野。
    返回同一份 report，便于链式调用。
    """
    ctx = {
        "camera": camera, "lens": lens, "light": light, "controller": controller,
        "accuracy": accuracy, "height_variation": height_variation,
        "moving": moving, "speed": speed,
        "fov_w": fov_w, "fov_h": fov_h, "wd_expect": wd_expect,
    }
    for c in report.checks:
        if c.status == "pass":
            continue
        c.remedies.extend(_fixes_for(c.name, ctx))
    return report


def _fixes_for(name: str, ctx: dict) -> list:
    cam = ctx["camera"]
    lens = ctx["lens"]
    acc = ctx["accuracy"]

    if name == "像素精度不足":
        fov_max_w = cam.width_px * acc
        fov_max_h = cam.height_px * acc
        fixes = [
            f"把视野缩到 ≤ {fov_max_w:g}×{fov_max_h:g} mm"
            f"（当前档位 {cam.width_px}×{cam.height_px} px × 目标精度 {acc:g}）"
        ]
        higher = next((t for t in SENSOR_TABLE
                       if t[1] >= cam.res_for_defect[0] and t[2] >= cam.res_for_defect[1]),
                      None)
        if higher:
            fixes.append(f"或升档至 {higher[0]:g}MP（{higher[1]}×{higher[2]}）")
        else:
            fixes.append("无更大面阵档位可覆盖该需求——走多拍拆分或线阵路径")
        return fixes

    if name == "焦距复算偏差":
        wd_needed = lens.f_recommend / lens.magnification
        return [
            f"把工作距离调到 {wd_needed:.1f} mm"
            f"（f ÷ β = {lens.f_recommend:g} ÷ {lens.magnification:.3f}），"
            f"{lens.f_recommend:g}mm 档即可自洽"
        ]

    if name == "景深" and ctx["height_variation"] <= 0:
        return ["提供被测物高度变化（--height-var，单位 mm）即可判定景深覆盖"]

    if name == "景深不足":
        beta = lens.magnification
        c_mm = 2 * cam.pixel_um / 1000.0   # 与 lens.py 同一容许弥散圆取法
        n_needed = ctx["height_variation"] * beta ** 2 / (2 * c_mm * (1 + beta))
        fixes = []
        if n_needed > 16:
            fixes.append(
                f"按公式需收光圈至约 F{n_needed:.0f}——已超出常规镜头光圈范围，"
                f"收光圈路线不可行"
            )
        else:
            fixes.append(
                f"光圈收至约 F{n_needed:.1f}"
                f"（景深估算按 F2.8，景深随 F 数线性增大）"
            )
        fixes.append("或改远心镜头（同倍率景深通常大一个量级）；或缩小视野（景深 ∝ 1/β²）")
        return fixes

    if name == "曝光拖影风险" and cam.exposure_max_us:
        limit = acc / ctx["speed"] * 1e6
        speed_max = acc / (cam.exposure_max_us * 1e-6)
        return [
            f"速度降至 ≤ {speed_max:.0f} mm/s（精度 ÷ 当前曝光），"
            f"或用频闪/爆闪把曝光压进 {limit:.0f} μs"
        ]

    if name == "增亮能力缺失":
        return [
            "控制器换 SPS（频闪，脉宽 120μs 级）或 BPS（爆闪，30μs 级）"
            "——增亮功能只有这两个系列有"
        ]

    if name == "光源覆盖不足":
        return [
            f"发光面至少 {ctx['fov_w'] * 1.2:.1f}×{ctx['fov_h'] * 1.2:.1f} mm"
            f"（视野 × 1.2 经验余量）"
        ]

    if name == "分辨率余量偏紧" and cam.fov_shot is None:
        higher = next((t for t in SENSOR_TABLE
                       if t[1] >= cam.res_for_defect[0] and t[2] >= cam.res_for_defect[1]
                       and t[0] > cam.megapixel), None)
        if higher:
            return [f"上调一档至 {higher[0]:g}MP（{higher[1]}×{higher[2]}）"]
        return []

    if name == "分辨率不足":
        return ["需求已超最大面阵档位——用多拍拆分（超规格自动启用）或线阵路径"]

    if name == "工作距离偏离" and ctx["wd_expect"] > 0:
        beta = lens.magnification
        best_f, best_wd = None, None
        for f in FOCAL_STEPS:
            wd = f / beta
            if best_wd is None or abs(wd - ctx["wd_expect"]) < abs(best_wd - ctx["wd_expect"]):
                best_f, best_wd = f, wd
        fixes = []
        if best_f is not None and best_f != lens.f_recommend:
            fixes.append(
                f"限高 {ctx['wd_expect']:g} mm 时改选 {best_f:g} mm 档"
                f"（对应 WD ≈ {best_wd:.0f} mm，按 f ÷ β 反算）"
            )
        if lens.f_calc > FOCAL_STEPS[-1]:
            fixes.append(
                f"计算焦距 {lens.f_calc:.1f}mm 已超常用档位上限：缩短工作距离、"
                f"换小靶面相机，或改 1× 远心（视野与工作距离固定）"
            )
        if not fixes:
            fixes.append(
                f"常用档位内无更优解：接受 WD {lens.wd_at_recommend:.0f} mm 并核对安装空间"
            )
        return fixes

    return []
