#!/usr/bin/env python3
"""以 web/lab.html 为唯一真源，生成 docs/lab.html（GitHub Pages 静态版）。

背景：web/ 与 docs/ 是同一套 UI 的两份副本，此前靠手工同步，
每次改几何都要在两套行号体系里重复改，已经漏过一次（docs 停留在旧几何）。
这里把两版的固定差异收敛成 5 条确定性替换，其余内容逐字继承。

用法：
  python scripts/build_docs.py           # 重新生成 docs/lab.html
  python scripts/build_docs.py --check   # 只校验产物是否已同步（CI 用）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "lab.html"
DST = ROOT / "docs" / "lab.html"

# (旧文本, 新文本, 说明)。每条必须唯一命中，否则直接失败，避免静默生成错页。
REPLACEMENTS: list[tuple[str, str, str]] = [
    (
        "<title>光学实验室 · 打光调试</title>",
        "<title>光学实验室 · 打光调试（在线静态版）</title>",
        "标题标注静态版",
    ),
    (
        '<script src="/vendor/three.min.js"></script>',
        '<script src="vendor/three.min.js"></script>\n<script src="lab-data.js"></script>',
        "three 改相对路径并引入本地数据层",
    ),
    (
        """async function fetchLab(series) {
  try {
    const res = await fetch('/api/lab?series=' + encodeURIComponent(series) +
      '&fov=' + S.fovW + 'x' + S.fovH + '&wd=' + S.wd);
    return await res.json();
  } catch (err) { return null; }
}""",
        """async function fetchLab(series) {
  // 静态站（GitHub Pages）：数据由 lab-data.js 本地生成，
  // 与 core/scene.py::build_lab 的返回值逐字段等价，无需 Python 后端。
  return LabData.buildLab(series, S.fovW, S.fovH, 'area', S.wd);
}""",
        "/api/lab 改 LabData.buildLab",
    ),
    (
        """fetch('/api/version').then(r => r.json()).then(d => { $('ver').textContent = d.version || ''; }).catch(() => {});""",
        """$('ver').textContent = LabData.version;""",
        "/api/version 改 LabData.version",
    ),
]


def build(text: str) -> str:
    for old, new, desc in REPLACEMENTS:
        hits = text.count(old)
        if hits != 1:
            raise SystemExit(f"[build_docs] 锚点「{desc}」匹配 {hits} 处，期望 1 处，已中止")
        text = text.replace(old, new)
    leftovers = [p for p in ("/api/lab", "/api/version") if p in text]
    if leftovers:
        raise SystemExit(f"[build_docs] 产物仍含动态接口引用：{', '.join(leftovers)}")
    return text


def main(argv: list[str]) -> int:
    if not SRC.exists():
        raise SystemExit(f"[build_docs] 真源不存在：{SRC}")
    out = build(SRC.read_text(encoding="utf-8"))

    if "--check" in argv:
        current = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if current != out:
            print("[build_docs] docs/lab.html 未同步，请运行 python scripts/build_docs.py")
            return 1
        print("[build_docs] docs/lab.html 已同步")
        return 0

    DST.write_text(out, encoding="utf-8", newline="\n")
    print(f"[build_docs] 已生成 {DST.relative_to(ROOT)}（{len(out)} 字符）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
