"""成像方案自动生成器 · 命令行入口

用法示例（通行做法那道练习题）：
  python run.py --task 表面划痕 --accuracy 0.01 --fov 12x10 --wd 130 --static

带样张的用法：
  python run.py --image data/sample.jpg --task 表面划痕 --accuracy 0.01 --fov 12x10

全程零第三方依赖：计算用标准库，图像解码复用系统 ffmpeg。
"""

import argparse
import os
import sys
import datetime

from core import __version__
from core.camera import select_camera
from core.lens import select_lens
from core.light import recommend_light
from core.controller import select_controller
from core.validate import validate
from core.report import build_html
from core.image_diag import diagnose, ImageDiagError
from core.yvison_export import build_camera_template, save_template

TASKS = [
    "尺寸测量", "轮廓定位", "透明件内部缺陷", "表面划痕", "凹坑压痕",
    "异物脏污", "平面字符", "二维码", "高反光金属", "曲面圆柱", "颜色判别",
]


def parse_fov(text: str) -> tuple:
    """解析 '12x10' / '12*10' / '12,10' 形式的视野。"""
    for sep in ("x", "X", "*", ",", "×"):
        if sep in text:
            a, b = text.split(sep, 1)
            return float(a), float(b)
    v = float(text)
    return v, v


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="机器视觉成像方案自动生成器：样品图 + 需求 → 相机/镜头/光源/控制器方案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--image", "-i", help="样品图路径（可选）；不给则跳过图像诊断")
    p.add_argument("--no-image", action="store_true", help="强制跳过图像诊断")
    p.add_argument("--drawing-txt", help="图纸文本文件；给了就由它反推视野、精度与任务")
    p.add_argument("--task", choices=TASKS, help="检测任务类型")
    p.add_argument("--accuracy", type=float, help="目标精度 mm，如 0.01")
    p.add_argument("--fov", help="视野 mm，格式 12x10")
    p.add_argument("--wd", type=float, default=130.0, help="期望工作距离 mm，默认 130")
    p.add_argument("--height-var", type=float, default=0.0, help="被测物高度变化 mm，默认 0")
    p.add_argument("--moving", action="store_true", help="运动拍摄（飞拍）")
    p.add_argument("--static", action="store_true", help="静止拍摄（默认）")
    p.add_argument("--speed", type=float, default=0.0, help="运动速度 mm/s，moving 时使用")
    p.add_argument("--need-color", action="store_true", help="必须保留颜色信息")
    p.add_argument("--boost-color", default="", help="需要突出的颜色：红/绿/蓝/黄/青/品红")
    p.add_argument("--suppress-color", default="", help="需要压掉的颜色")
    p.add_argument("--feature-px", type=int, default=3, help="缺陷至少占几个像素，默认 3")
    p.add_argument("--fov-margin", type=float, default=0.0, help="视野余量，0.2 表示每边放大 20%%")
    p.add_argument("--channels", type=int, default=1, help="光源接线路数（不是光源个数），默认 1")
    p.add_argument("--channel-power", type=float, default=10.0, help="单路功率 W，默认 10")
    p.add_argument("--program", action="store_true", help="需要程序控制亮度（要串口/网口）")
    p.add_argument("--timeseq", action="store_true", help="需要多路分时/分区域点亮")
    p.add_argument("--stable", action="store_true", help="需要长期亮度稳定")
    p.add_argument("--outdir", default="out", help="方案书输出目录，默认 out")
    p.add_argument("--yvison-camera",
                   help="Yvison 的 User_Camera.xml 路径；给了就额外生成相机参数模板副本")
    p.add_argument("--yvison-brand", default="海康", help="模板里的品牌组名，默认 海康")
    args = p.parse_args(argv)

    # --- 0. 图纸驱动：从公差与外形反推检测条件（可选）---
    if args.drawing_txt:
        from core.drawing import parse_drawing
        try:
            with open(args.drawing_txt, encoding="utf-8", errors="ignore") as f:
                d = parse_drawing(f.read())
        except OSError as e:
            p.error(f"读不了图纸文本：{e}")
        args.fov = f"{d.fov_w}x{d.fov_h}"
        args.accuracy = d.accuracy
        args.task = args.task or d.task
        print("=" * 62)
        print(f"图纸反推　置信度 {d.confidence}")
        for s in d.steps:
            print(f"  · {s}")
        for n in d.notes:
            print(f"  ! {n}")
        print("=" * 62)

    missing = [k for k in ("task", "accuracy", "fov") if getattr(args, k) is None]
    if missing:
        p.error("缺少参数：" + " ".join("--" + m for m in missing) + "（也可以给 --drawing-txt 让图纸来推）")

    moving = args.moving and not args.static
    fov_w, fov_h = parse_fov(args.fov)

    # --- 1. 图像诊断（可选，失败自动降级）---
    diag = None
    diag_note = ""
    if args.image and not args.no_image:
        try:
            diag = diagnose(args.image)
        except ImageDiagError as e:
            diag_note = f"图像诊断跳过：{e}"
            print(f"[警告] {diag_note}", file=sys.stderr)
    elif not args.no_image:
        diag_note = "未提供样张，跳过图像诊断"

    # --- 2. 相机 ---
    cam = select_camera(
        fov_w=fov_w, fov_h=fov_h, accuracy=args.accuracy,
        moving=moving, speed=args.speed, need_color=args.need_color,
        feature_px=args.feature_px, fov_margin=args.fov_margin,
    )
    fov_w_eff = fov_w * (1 + args.fov_margin)
    fov_h_eff = fov_h * (1 + args.fov_margin)

    # --- 3. 镜头 ---
    lens = select_lens(
        sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
        fov_w=fov_w_eff, fov_h=fov_h_eff, wd=args.wd,
        pixel_um=cam.pixel_um,
        need_precision_measure=(args.task == "尺寸测量"),
        height_variation=args.height_var,
    )

    # --- 4. 光源 ---
    light = recommend_light(
        task=args.task, fov_w=fov_w_eff, fov_h=fov_h_eff,
        boost_color=args.boost_color, suppress_color=args.suppress_color,
        diag=diag.as_dict() if diag else None,
    )

    # --- 5. 控制器 ---
    ctrl = select_controller(
        light_channels=args.channels, channel_power_w=args.channel_power,
        need_program_control=args.program,
        exposure_max_us=cam.exposure_max_us,
        need_time_sequence=args.timeseq,
        need_stable_brightness=args.stable,
    )

    # --- 6. 自检复算 ---
    val = validate(
        camera=cam, lens=lens, light=light, controller=ctrl,
        accuracy=args.accuracy, height_variation=args.height_var,
        moving=moving, speed=args.speed,
        fov_w=fov_w_eff, fov_h=fov_h_eff, wd_expect=args.wd,
    )

    # --- 7. 出方案书 ---
    inputs = {
        "task": args.task, "accuracy": args.accuracy,
        "fov": (fov_w, fov_h), "wd": args.wd,
        "moving": moving, "speed": args.speed,
        "need_color": args.need_color,
        "boost_color": args.boost_color, "suppress_color": args.suppress_color,
        "height_var": args.height_var,
    }
    html_text = build_html(inputs, diag, cam, lens, light, ctrl, val, version=__version__)
    os.makedirs(args.outdir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.outdir, f"spec_{stamp}.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_text)

    # --- 8. 控制台摘要（答辩现场可直接念）---
    print("=" * 62)
    print(f"成像方案　{args.task}　精度 {args.accuracy:g}mm　视野 {fov_w:g}×{fov_h:g}mm")
    print("=" * 62)
    print(f"相机    {cam.megapixel:g}MP  {cam.width_px}×{cam.height_px}  "
          f"{cam.sensor_name}  {cam.color_mode}")
    print(f"        像素精度 {cam.pixel_accuracy_mm:.4f} mm/px  {cam.shutter}")
    print(f"镜头    {lens.f_recommend:g}mm  WD {lens.wd_at_recommend:.0f}mm  "
          f"视场角 {lens.fov_angle_deg:.1f}°  景深≈{lens.dof_estimate_mm:.3f}mm")
    print(f"光源    {light.form}　{light.series}{(' ' + light.angle) if light.angle else ''}"
          f" / {light.direction} / {light.color}  "
          f"发光面 {light.size_mm[0]:g}×{light.size_mm[1]:g}mm"
          f"{'  需偏振' if light.polarization else ''}")
    print(f"控制器  {ctrl.model_string}  {ctrl.series_full}")
    print(f"自检    {val.overall}  （通过 {sum(1 for c in val.checks if c.status == 'pass')}"
          f" / 警告 {val.warn_count} / 不通过 {val.fail_count}）")
    if diag:
        print(f"图像    灰度差 {diag.gray_diff:.1f}  过曝 {diag.overexposed_ratio:.2%}  "
              f"判定 {diag.grade}")
    for c in val.checks:
        if c.status != "pass":
            print(f"  [{c.status.upper()}] {c.name}：{c.detail}")
    if diag_note:
        print(f"  注：{diag_note}")
    print("-" * 62)
    print(f"方案书  {os.path.abspath(out_path)}")

    # --- 9. 导出 Yvison 相机参数模板（可选，只生成副本不覆盖原文件）---
    if args.yvison_camera:
        data, changes, err = build_camera_template(
            cam, args.yvison_camera, moving=moving, brand=args.yvison_brand
        )
        if err:
            print(f"[警告] 未生成 Yvison 模板：{err}", file=sys.stderr)
        else:
            cfg_path = os.path.join(
                args.outdir, f"User_Camera_{args.yvison_brand}_方案值.xml"
            )
            save_template(data, cfg_path)
            print("-" * 62)
            print(f"Yvison 相机模板（{args.yvison_brand} 组）")
            if changes:
                for real, old, new in changes:
                    print(f"  {real}: {old or '(空)'} → {new}")
            else:
                print("  与模板里的现值一致，无需改动")
            print(f"  {os.path.abspath(cfg_path)}")
            print("  用法：核对无误后，替换 Config/Parameter/User_Camera.xml 并重启 Yvison")
            print("  注意：① 分辨率须相机实际支持（超规格相机不接受该值）")
            print("        ② 曝光是上限，实际设置建议取 80% 留余量")
            print("        ③ 光源参数未包含，需软件运行时读 get_hardware_config led 确认字段")
    return 0


if __name__ == "__main__":
    sys.exit(main())
