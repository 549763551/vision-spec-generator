"""图像质量诊断。

为什么不用 OpenCV：答辩现场环境不可控，本模块坚持零第三方依赖。
图像解码复用系统已有的 ffmpeg，转成 PGM（P5 格式自带宽度/高度头），
再用标准库解析字节流。ffmpeg 缺失时抛出 ImageDiagError，
由上层降级为"仅做选型计算，跳过图像诊断"。

诊断项与判据出处：行业通用选型方法（什么才算一张好图）
  1. 特征与背景的灰度差 ≥ 30 才算稳定
  2. 整体均匀，不能有过曝亮斑；过曝丢细节、欠曝看不见
  3. 色彩还原真实（本模块先做灰度判据，颜色判据留待彩色通道）
"""

from dataclasses import dataclass, field
import shutil
import subprocess


class ImageDiagError(Exception):
    """图像无法解码时抛出。"""


@dataclass
class ImageDiag:
    width: int
    height: int
    mean: float
    std: float
    gray_diff: float          # Otsu 两类均值差，对应通行做法"灰度差 ≥ 30"
    overexposed_ratio: float  # 灰度 ≥ 250 的像素占比
    underexposed_ratio: float # 灰度 ≤ 5 的像素占比
    lap_var: float            # 拉普拉斯方差，衡量清晰度
    strong_edge_ratio: float  # 梯度 > 30 的像素占比，衡量真实边缘有多少
    otsu_threshold: int
    grade: str                # 合格 / 临界 / 不合格
    issues: list = field(default_factory=list)   # 影响判级
    notes: list = field(default_factory=list)    # 仅供阅读，不影响判级
    steps: list = field(default_factory=list)

    def as_dict(self) -> dict:
        """供 light.recommend_light 的 diag 参数使用。"""
        return {
            "gray_diff": self.gray_diff,
            "overexposed_ratio": self.overexposed_ratio,
            "underexposed_ratio": self.underexposed_ratio,
            "lap_var": self.lap_var,
            "strong_edge_ratio": self.strong_edge_ratio,
        }


def _find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise ImageDiagError(
            "找不到 ffmpeg。图像诊断需要 ffmpeg 解码，"
            "可跳过图像诊断只做选型计算（加 --no-image）"
        )
    return exe


def _decode_pgm(path: str) -> tuple:
    """调用 ffmpeg 把任意图片转成灰度 PGM，返回 (宽, 高, 像素字节)。"""
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg, "-v", "error", "-i", path,
        "-vf", "format=gray",
        "-f", "image2pipe", "-vcodec", "pgm", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise ImageDiagError(f"ffmpeg 解码超时：{path}")
    if proc.returncode != 0 or not proc.stdout:
        msg = proc.stderr.decode("utf-8", "ignore").strip()[:200]
        raise ImageDiagError(f"ffmpeg 无法解码该文件：{path}\n{msg}")

    data = proc.stdout
    # PGM 头：P5\n<宽> <高>\n<最大灰度>\n，允许注释行
    pos = 0
    tokens = []
    while len(tokens) < 4 and pos < len(data):
        # 跳过空白
        while pos < len(data) and data[pos:pos + 1].isspace():
            pos += 1
        # 跳过注释
        if data[pos:pos + 1] == b"#":
            while pos < len(data) and data[pos:pos + 1] != b"\n":
                pos += 1
            continue
        start = pos
        while pos < len(data) and not data[pos:pos + 1].isspace():
            pos += 1
        tokens.append(data[start:pos])
    pos += 1  # 头之后的一个空白

    if len(tokens) < 4 or tokens[0] != b"P5":
        raise ImageDiagError("PGM 头解析失败，ffmpeg 输出格式异常")
    width, height = int(tokens[1]), int(tokens[2])
    pixels = data[pos:pos + width * height]
    if len(pixels) < width * height:
        raise ImageDiagError(
            f"像素数据不完整：期望 {width * height} 字节，实得 {len(pixels)}"
        )
    return width, height, pixels


def _otsu(hist: list) -> int:
    """Otsu 阈值：让前景/背景两类间方差最大。纯 Python 实现，256 次循环。"""
    total = sum(hist)
    if total == 0:
        return 0
    sum_all = sum(i * h for i, h in enumerate(hist))
    sum_b = 0.0
    w_b = 0
    best_t, best_var = 0, -1.0
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return best_t


def diagnose(path: str) -> ImageDiag:
    """对一张图片做成像质量诊断。"""
    width, height, pixels = _decode_pgm(path)
    n = len(pixels)

    # --- 基础统计 ---
    hist = [0] * 256
    s = 0
    over = 0
    under = 0
    for v in pixels:
        hist[v] += 1
        s += v
        if v >= 250:
            over += 1
        elif v <= 5:
            under += 1
    mean = s / n
    var = sum((v - mean) ** 2 for v in pixels) / n
    std = var ** 0.5

    steps = [
        f"图像尺寸 {width}×{height}，灰度均值 {mean:.1f}，标准差 {std:.1f}",
    ]

    # --- 灰度差：Otsu 分割后两类均值之差（通行做法"灰度差 ≥ 30"）---
    thr = _otsu(hist)
    w_b = sum(hist[:thr + 1])
    w_f = n - w_b
    if w_b and w_f:
        m_b = sum(i * hist[i] for i in range(thr + 1)) / w_b
        m_f = sum(i * hist[i] for i in range(thr + 1, 256)) / w_f
        gray_diff = abs(m_f - m_b)
    else:
        gray_diff = 0.0
    steps.append(
        f"Otsu 阈值 {thr}，背景均值 {m_b if w_b and w_f else 0:.1f} / "
        f"前景均值 {m_f if w_b and w_f else 0:.1f}，灰度差 {gray_diff:.1f}"
    )

    # --- 清晰度：拉普拉斯方差 + 强边缘占比 ---
    # 为什么不用"相邻像素差分均值"：大片均匀背景会把均值稀释到 2~3，
    # 清晰图和模糊图都判成"模糊"。拉普拉斯方差对边缘更敏感，
    # 在自建对照组上（原图 / σ=1.5 / σ=3 模糊）实测为 83 / 8 / 2，区分度足够。
    stride = max(1, int((width * height / 1_000_000) ** 0.5))
    lap_sum = 0.0
    lap_sq = 0.0
    n_lap = 0
    strong = 0
    n_edge = 0
    for y in range(stride, height - stride, stride):
        b = y * width
        for x in range(stride, width - stride, stride):
            c = pixels[b + x]
            lap = 4 * c - (
                pixels[b - stride * width + x] + pixels[b + stride * width + x]
                + pixels[b + x - stride] + pixels[b + x + stride]
            )
            lap_sum += lap
            lap_sq += lap * lap
            n_lap += 1
            if abs(c - pixels[b + x + stride]) > 30:
                strong += 1
            n_edge += 1
    lap_mean = lap_sum / n_lap if n_lap else 0.0
    lap_var = (lap_sq / n_lap - lap_mean ** 2) if n_lap else 0.0
    strong_ratio = strong / n_edge if n_edge else 0.0
    steps.append(
        f"清晰度：拉普拉斯方差 {lap_var:.0f}，强边缘占比 {strong_ratio:.2%}"
        f"（降采样步长 {stride}，{n_lap} 个像素参与）"
    )

    over_r = over / n
    under_r = under / n
    steps.append(f"过曝像素占比 {over_r:.2%}，欠曝像素占比 {under_r:.2%}")

    # --- 判级（判据来自通行做法，阈值按工程经验分严重/提示两级）---
    # issues 影响判级；notes 只作说明，不改变结论。
    issues = []
    notes = []
    severe = 0
    if gray_diff < 20:
        issues.append(f"灰度差 {gray_diff:.1f} 远低于 30，特征与背景几乎分不开")
        severe += 1
    elif gray_diff < 30:
        issues.append(f"灰度差 {gray_diff:.1f} 未达 30，算法阈值会很敏感")
    if over_r > 0.10:
        issues.append(f"过曝 {over_r:.1%}，亮部细节已丢失")
        severe += 1
    elif over_r > 0.03:
        notes.append(
            f"亮部接近饱和（{over_r:.1%} 像素 ≥ 250）：白色产品本身合法，"
            f"只需确认检测区不落在过曝位置"
        )
    if under_r > 0.30:
        issues.append(f"欠曝 {under_r:.1%}，画面过暗")
        severe += 1
    if std < 15:
        issues.append(f"整体标准差 {std:.1f} 偏低，画面平淡、对比不足")
        severe += 1
    if mean < 40:
        notes.append(
            f"整体灰度均值 {mean:.0f} 偏暗：暗场照明尤其费光，"
            f"需提高光强或延长曝光（加增益会同时放大噪声）"
        )
    # 模糊 vs 低纹理要分开：
    #   方差低 + 完全没边缘 → 是样品本身平整/无特征，不是失焦
    #   方差低 + 仍有边缘但很软 → 才是离焦或解析力不足
    if lap_var < 15 and strong_ratio >= 0.001:
        issues.append(
            f"拉普拉斯方差 {lap_var:.0f} 偏低但仍有 {strong_ratio:.2%} 强边缘，"
            f"边缘偏软：可能离焦、镜头解析力不足或光源角度过正"
        )
        severe += 1
    elif lap_var < 8 and strong_ratio < 0.001:
        issues.append(
            f"画面几乎没有纹理与边缘（方差 {lap_var:.0f}），"
            f"确认样品/ROI 是否有效，或视野是否落在空白区域"
        )

    if severe:
        grade = "不合格"
    elif issues:
        grade = "临界"
    else:
        grade = "合格"

    return ImageDiag(
        width=width, height=height, mean=mean, std=std,
        gray_diff=gray_diff, overexposed_ratio=over_r,
        underexposed_ratio=under_r, lap_var=lap_var, strong_edge_ratio=strong_ratio,
        otsu_threshold=thr, grade=grade, issues=issues, notes=notes, steps=steps,
    )
