"""从产品图纸反推检测需求。

真实工作流里，工程师拿到的不是"四行参数"，是一张图纸。
图纸上有外形尺寸、有公差、有外观要求，检测条件其实是这些数字推出来的。

本模块做两件事：
  1. 从图纸文本里抽尺寸与公差
  2. 按工程惯例反推视野、精度、检测任务

依据的工程惯例（不是某家课件）：
  · 测量不确定度 1:5 —— 要判定 ±T 的公差，量具本身的误差应小于公差带的 1/5
  · 缺陷占 3 像素 —— 一个缺陷至少要落在 3 个像素上才检得稳（与相机选型同一套逻辑）
  · 视野留 20% 余量 —— 工件不会永远摆在正中间

输入是文本（由 PDF 转文本工具得到），因此本模块不依赖任何 PDF 库。
"""

from dataclasses import dataclass, field
import re


@dataclass
class DrawingSpec:
    fov_w: float
    fov_h: float
    accuracy: float
    task: str
    max_dim: float
    second_dim: float | None
    min_tol_band: float | None
    min_defect: float | None
    tolerances: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    confidence: str = "低"


# 这些行里的数字与检测尺寸无关，先剔除
NOISE = re.compile(
    r"ppm|RoHS|REACH|DIRECTIVE|REGULATION|UL 94|ISO|PFAS|MCSS|"
    r"www\.|http|PAGE|SHEET|REV|DATE|ECN|DRWN|CHK|APPR|PROJECTION",
    re.I,
)

PAT_SYM = re.compile(r"±\s*(\d+(?:\.\d+)?)\s*(°)?")
PAT_PLUS = re.compile(r"\+\s*(\d+(?:\.\d+)?)")
PAT_MINUS = re.compile(r"^-\s*(\d+(?:\.\d+)?)")
PAT_NUM = re.compile(r"(?<![\d.])(\d{1,3}\.\d{1,2})(?![\d.])")


def parse_drawing(text: str, margin: float = 0.2,
                  sigma: float = 5.0, defect_px: int = 3) -> DrawingSpec:
    """解析图纸文本，反推检测需求。

    margin    : 视野余量，0.2 表示四周各留 20%
    sigma     : 测量不确定度比例，5 表示量具误差要小于公差带的 1/5
    defect_px : 一个缺陷至少占几个像素
    """
    lines = text.splitlines()
    tolerances = []          # (公差带宽度, 原始描述, 类别)
    dims = []                # 尺寸
    steps = []
    notes = []

    for i, line in enumerate(lines):
        if NOISE.search(line):
            continue

        # --- 对称公差 ±x ---
        for m in PAT_SYM.finditer(line):
            if m.group(2):        # 带 ° 的是角度公差，不参与尺寸精度
                continue
            v = float(m.group(1))
            band = 2 * v
            kind = "一般公差" if "PLACE" in line.upper() else "特征公差"
            tolerances.append((band, f"±{v}", kind))

        # --- 不对称公差 +a / -b（PDF 提取后常常折成两行）---
        mp = PAT_PLUS.search(line)
        if mp and "±" not in line:
            a = float(mp.group(1))
            b = None
            if i + 1 < len(lines):
                mn = PAT_MINUS.match(lines[i + 1].strip())
                if mn:
                    b = float(mn.group(1))
            if b is not None:
                tolerances.append((a + b, f"+{a}/-{b}", "特征公差"))

        # --- 尺寸：把公差片段抹掉后剩下的带小数数字 ---
        cleaned = PAT_SYM.sub(" ", line)
        cleaned = re.sub(r"[+-]\s*\d+(?:\.\d+)?", " ", cleaned)
        for m in PAT_NUM.finditer(cleaned):
            v = float(m.group(1))
            if 0.5 <= v <= 200:
                dims.append(v)

    # --- 外观类要求：最大允许毛刺/划伤尺寸 ---
    min_defect = None
    m = re.search(r"(?:NOT\s+EXCEED|MAX\.?|SHALL\s+NOT\s+EXCEED)\s*(\d+(?:\.\d+)?)\s*MM", text, re.I)
    if m:
        min_defect = float(m.group(1))
        notes.append(f"图纸规定最大允许毛刺 {min_defect} mm，这是外观检测的最小可检尺寸")

    # --- 取最严的公差带 ---
    feature = [t for t in tolerances if t[2] == "特征公差"]
    pool = feature or tolerances
    min_band = min((t[0] for t in pool), default=None)
    tightest = min(pool, key=lambda t: t[0]) if pool else None

    # --- 视野：取最大两个外形尺寸 ---
    uniq = sorted(set(dims), reverse=True)
    if len(uniq) >= 2:
        max_dim, second = uniq[0], uniq[1]
        if second < max_dim * 0.4:          # 第二大的太悬殊，说明是特征尺寸而非外形
            second = max_dim * 0.75
    elif uniq:
        max_dim = uniq[0]
        second = max_dim * 0.75
    else:
        max_dim = second = 0.0

    fov_w = round(max_dim * (1 + margin), 2)
    fov_h = round(second * (1 + margin), 2)

    # --- 最小可检特征：缺陷尺寸优先，纯测量场景才退回公差折算 ---
    # 注意语义：这里给相机模块的是"最小特征尺寸"，相机再按"占 N 个像素"换算分辨率。
    # 公差带 ÷ sigma 是"测量分辨力"，靠亚像素实现，不该再乘一次像素数——
    # 早期版本在这里取了两者的较小值，导致同一个约束被乘两次，分辨率虚高 4 倍。
    measure_need = (min_band / sigma) if min_band else None
    if measure_need:
        steps.append(
            f"最严公差 {tightest[1]}（公差带 {min_band:g} mm）→ 按 1:{sigma:g} 折算，"
            f"测量分辨力需求 {measure_need:.4f} mm（靠亚像素实现，不额外占像素）"
        )

    if min_defect:
        accuracy = round(min_defect, 4)
        task = "表面划痕" if (measure_need is None or min_defect <= measure_need * 3) else "尺寸测量"
        steps.append(
            f"最小可检特征取毛刺/缺陷 {min_defect:g} mm（要占 {defect_px} 个像素，"
            f"对应像素精度 {min_defect / defect_px:.4f} mm/px）"
        )
        if measure_need:
            pixel_acc = min_defect / defect_px
            verdict = "同时满足" if pixel_acc <= measure_need else "略低于"
            steps.append(
                f"该像素精度 {pixel_acc:.4f} mm/px {verdict}测量分辨力需求 {measure_need:.4f} mm"
            )
    elif measure_need:
        accuracy = round(measure_need, 4)
        task = "尺寸测量"
        steps.append(f"图纸无外观要求 → 按测量分辨力 {measure_need:.4f} mm 作为最小可检特征")
    else:
        accuracy = 0.05
        task = "尺寸测量"
        notes.append("图纸里没有找到公差标注，精度按 0.05mm 估值，需人工确认")

    steps.insert(0, f"外形最大尺寸 {max_dim:g} mm，次大 {second:g} mm，视野留 {margin:.0%} 余量 → {fov_w}×{fov_h} mm")
    if tightest:
        steps.append(f"共识别 {len(tolerances)} 条公差，其中最严的是 {tightest[1]}")

    if min_band and min_defect:
        confidence = "高"
    elif min_band or min_defect:
        confidence = "中"
    else:
        confidence = "低"

    if min_band and min_defect:
        notes.append(
            "图纸同时给出尺寸公差与允许毛刺：量尺寸靠背光看轮廓，看毛刺靠低角度暗场，"
            "一套光难以兼顾，建议双光源分时点亮，控制器改选 TPS 多路时序"
        )

    return DrawingSpec(
        fov_w=fov_w, fov_h=fov_h, accuracy=accuracy, task=task,
        max_dim=max_dim, second_dim=(second if second else None),
        min_tol_band=min_band, min_defect=min_defect,
        tolerances=[(f"{t[1]}", t[0], t[2]) for t in sorted(tolerances, key=lambda x: x[0])],
        steps=steps, notes=notes, confidence=confidence,
    )
