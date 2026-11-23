"""演示服务：本地网页版交互界面。

为什么做这个：命令行演示要打一长串参数，投影上看不清、现场容易打错。
这个服务把同一套计算引擎包成网页：左侧拖图填参数，右侧实时出结论。

设计取舍：
  1. 零第三方依赖，只用标准库 http.server（答辩现场不装包）
  2. 图片走 base64 + JSON，不用 multipart 解析（标准库 cgi 已废弃）
  3. 三个预设场景对应演示脚本，现场点按钮而不是打字
  4. 同一套 core 模块，命令行和网页输出完全一致——不是两套代码

启动：
  python demo_server.py            默认 http://127.0.0.1:8848
  python demo_server.py 9000       指定端口
"""

import base64
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core import __version__
from core.camera import select_camera, task_requires_color
from core.lens import select_lens
from core.light import recommend_light
from core.controller import select_controller
from core.validate import validate
from core.remedy import attach_remedies
from core.report import build_html
from core.image_diag import diagnose, ImageDiagError
from core.drawing import parse_drawing
from core.procedure import build_procedure
from core.scene import build_scene
from core.yvison_export import build_camera_template, save_template

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")
DIST = os.path.join(ROOT, "ui", "dist")
OUT = os.path.join(ROOT, "out")
YVISON_XML = r"F:\Yvisionn\Yvison\Config\Parameter\User_Camera.xml"

TASKS = [
    "尺寸测量", "轮廓定位", "透明件内部缺陷", "表面划痕", "凹坑压痕",
    "异物脏污", "平面字符", "二维码", "高反光金属", "曲面圆柱", "颜色判别",
]

# PDF 转文本工具：优先 PATH，其次应用内置位置；都没有就提示用户给 txt
PDF_CLI_CANDIDATES = [
    "workbuddy-pdf",
    os.path.expanduser(r"~\.workbuddy\external-packages\pdf-cli\workbuddy-pdf.exe"),
]


SAMPLE_DRAWING = os.path.join(ROOT, "data", "samples", "sample_drawing.txt")


def drawing_result(text: str) -> dict:
    """图纸文本 → 检测需求。上传与示例共用同一份输出结构。"""
    d = parse_drawing(text)
    return {
        "ok": True,
        "fov_w": d.fov_w, "fov_h": d.fov_h,
        "accuracy": d.accuracy, "task": d.task,
        "confidence": d.confidence,
        "max_dim": d.max_dim, "second_dim": d.second_dim,
        "min_tol_band": d.min_tol_band, "min_defect": d.min_defect,
        "steps": d.steps, "notes": d.notes,
        "tolerances": [{"raw": t[0], "band": t[1], "kind": t[2]} for t in d.tolerances[:12]],
        "chars": len(text),
    }


def find_pdf_cli():
    for c in PDF_CLI_CANDIDATES:
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    return None


def read_drawing_pdf(b64: str) -> str:
    """把上传的 PDF 转成文本。找不到工具时抛异常，由上层转成提示。"""
    cli = find_pdf_cli()
    if not cli:
        raise RuntimeError("本机没有 PDF 转文本工具，请改上传 .txt 图纸文本")
    os.makedirs(OUT, exist_ok=True)
    stamp = f"{datetime.datetime.now():%H%M%S%f}"
    pdf_path = os.path.join(OUT, f"_draw_{stamp}.pdf")
    txt_path = os.path.join(OUT, f"_draw_{stamp}.txt")
    with open(pdf_path, "wb") as f:
        f.write(base64.b64decode(b64.split(",")[-1]))
    try:
        proc = subprocess.run([cli, pdf_path, txt_path, "-f", "txt", "-q"],
                              capture_output=True, timeout=120)
        if proc.returncode != 0 or not os.path.exists(txt_path):
            msg = proc.stderr.decode("utf-8", "ignore")[:200]
            raise RuntimeError(f"PDF 转文本失败：{msg or '未知原因'}")
        with open(txt_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    finally:
        for p in (pdf_path, txt_path):
            try:
                os.remove(p)
            except OSError:
                pass


def compute(payload: dict) -> dict:
    """跑一次完整推算，返回给前端渲染的字典。"""
    task = payload.get("task", "表面划痕")
    accuracy = float(payload.get("accuracy", 0.05))
    fov_w = float(payload.get("fov_w", 40))
    fov_h = float(payload.get("fov_h", 33))
    wd = float(payload.get("wd", 300))
    moving = bool(payload.get("moving", False))
    speed = float(payload.get("speed", 0) or 0)
    need_color = bool(payload.get("need_color", False)) or task_requires_color(task)
    height_var = float(payload.get("height_var", 0) or 0)
    channels = int(payload.get("channels", 1))
    channel_power = float(payload.get("channel_power", 10))
    program = bool(payload.get("program", False))
    surface = str(payload.get("surface", "") or "")

    # 图像诊断（可选，失败降级）
    diag = None
    diag_error = ""
    img_b64 = payload.get("image")
    sample = payload.get("use_sample")
    if sample:
        # 演示用内置样张，省掉现场找文件这一步
        cand = os.path.join(ROOT, "data", "samples", "sample_part.png")
        if not os.path.exists(cand):
            cand = os.path.join(ROOT, "data", "samples", "image163.png")
        if os.path.exists(cand):
            try:
                diag = diagnose(cand)
            except ImageDiagError as e:
                diag_error = str(e)[:160]
        else:
            diag_error = "内置样张缺失：data/samples/sample_part.png"
    elif img_b64:
        try:
            raw = base64.b64decode(img_b64.split(",")[-1])
            # 按声明的 MIME 定后缀，便于排查；ffmpeg 本身按内容识别，后缀不影响解码
            head = img_b64[:40].lower()
            ext = "png"
            if "image/jpeg" in head or "image/jpg" in head:
                ext = "jpg"
            elif "image/webp" in head:
                ext = "webp"
            elif "image/bmp" in head:
                ext = "bmp"
            elif "image/tiff" in head:
                ext = "tif"
            tmp = os.path.join(OUT, f"_upload_{datetime.datetime.now():%H%M%S%f}.{ext}")
            os.makedirs(OUT, exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(raw)
            try:
                diag = diagnose(tmp)
            finally:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except (ImageDiagError, ValueError, OSError) as e:
            diag_error = str(e)[:160]

    cam = select_camera(fov_w=fov_w, fov_h=fov_h, accuracy=accuracy,
                        moving=moving, speed=speed, need_color=need_color)
    # 超规格时相机按多拍拆分：镜头/光源/自检改用单幅视野
    if cam.fov_shot:
        fov_w, fov_h = cam.fov_shot
    lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                       fov_w=fov_w, fov_h=fov_h, wd=wd, pixel_um=cam.pixel_um,
                       need_precision_measure=(task == "尺寸测量"),
                       height_variation=height_var)
    light = recommend_light(task=task, fov_w=fov_w, fov_h=fov_h,
                            diag=diag.as_dict() if diag else None,
                            surface=surface)
    ctrl = select_controller(light_channels=channels, channel_power_w=channel_power,
                             need_program_control=program,
                             exposure_max_us=cam.exposure_max_us)
    val = validate(camera=cam, lens=lens, light=light, controller=ctrl,
                   accuracy=accuracy, height_variation=height_var,
                   moving=moving, speed=speed, fov_w=fov_w, fov_h=fov_h,
                   wd_expect=wd)
    attach_remedies(val, cam, lens, light, ctrl,
                    accuracy=accuracy, height_variation=height_var,
                    moving=moving, speed=speed, fov_w=fov_w, fov_h=fov_h,
                    wd_expect=wd)

    # 流程作业指导书（通用节点链，不绑软件）
    proc = build_procedure(
        task=task, pixel_acc=cam.pixel_accuracy_mm, accuracy_mm=accuracy,
        fov_w=fov_w, fov_h=fov_h, cam_w=cam.width_px, cam_h=cam.height_px,
        gray_diff=(diag.gray_diff if diag else None),
    )

    # 生成一份完整方案书，供"打开完整报告"用
    inputs = {"task": task, "accuracy": accuracy, "fov": (fov_w, fov_h), "wd": wd,
              "moving": moving, "speed": speed, "need_color": need_color,
              "boost_color": "", "suppress_color": "", "height_var": height_var,
              "surface": surface}
    html_text = build_html(inputs, diag, cam, lens, light, ctrl, val, version=__version__)
    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_name = f"spec_{stamp}.html"
    with open(os.path.join(OUT, report_name), "w", encoding="utf-8") as f:
        f.write(html_text)

    # Yvison 模板（有原文件才导）
    yvison_changes = []
    if os.path.exists(YVISON_XML):
        data, changes, err = build_camera_template(cam, YVISON_XML, moving=moving)
        if not err:
            save_template(data, os.path.join(OUT, "User_Camera_海康_方案值.xml"))
            yvison_changes = [{"field": r, "old": str(o) or "(空)", "new": str(nv)}
                              for r, o, nv in changes]

    return {
        "ok": True,
        "version": __version__,
        "camera": {
            "mp": cam.megapixel, "w": cam.width_px, "h": cam.height_px,
            "sensor": cam.sensor_name, "color": cam.color_mode,
            "accuracy": round(cam.pixel_accuracy_mm, 4),
            "shutter": cam.shutter,
            "interface": cam.interface, "mount": cam.mount, "depth": cam.pixel_depth,
            "exposure": (round(cam.exposure_max_us, 1) if cam.exposure_max_us else None),
            "fps": (round(cam.fps_min, 2) if cam.fps_min else None),
            "shots_w": cam.shots_w, "shots_h": cam.shots_h,
            "fov_shot": (list(cam.fov_shot) if cam.fov_shot else None),
            "steps": cam.steps,
        },
        "lens": {
            "f": lens.f_recommend, "f_calc": round(lens.f_calc, 2),
            "alt": lens.f_alt, "wd": round(lens.wd_at_recommend),
            "wd_alt": (round(lens.wd_at_alt) if lens.wd_at_alt else None),
            "angle": round(lens.fov_angle_deg, 1),
            "mag": round(lens.magnification, 2),
            "dof": round(lens.dof_estimate_mm, 3),
            "tele": lens.need_telecentric,
            "steps": lens.steps,
        },
        "light": {
            "direction": light.direction, "field": light.field_type,
            "form": light.form, "series": light.series, "angle": light.angle,
            "color": light.color, "size": list(light.size_mm),
            "polar": light.polarization,
            "steps": light.steps,
        },
        "controller": {
            "series": ctrl.series, "full": ctrl.series_full,
            "model": ctrl.model_string, "v": ctrl.voltage,
            "p": ctrl.power_w, "ch": ctrl.channels,
            "serial": ctrl.has_serial, "boost": ctrl.has_boost,
            "steps": ctrl.steps,
        },
        "validate": {
            "overall": val.overall,
            "pass": sum(1 for c in val.checks if c.status == "pass"),
            "warn": val.warn_count, "fail": val.fail_count,
            "checks": [{"name": c.name, "status": c.status,
                        "detail": c.detail, "rule": c.rule,
                        "remedies": c.remedies} for c in val.checks],
        },
        "procedure": [{"no": x.no, "node": x.node, "params": x.params, "note": x.note} for x in proc],
        "diag": ({
            "w": diag.width, "h": diag.height, "gray_diff": round(diag.gray_diff, 1),
            "over": round(diag.overexposed_ratio * 100, 2),
            "lap": round(diag.lap_var), "edge": round(diag.strong_edge_ratio * 100, 2),
            "grade": diag.grade, "issues": diag.issues, "notes": diag.notes,
        } if diag else None),
        "diag_error": diag_error,
        "report_url": f"/out/{report_name}",
        "yvison": yvison_changes,
        "yvison_available": os.path.exists(YVISON_XML),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 演示现场不刷日志

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/assets/"):
            # React 构建产物（哈希文件名，可长缓存）
            name = os.path.basename(urllib.parse.unquote(path[8:]))
            fp = os.path.join(DIST, "assets", name)
            if os.path.exists(fp):
                ctype = ("text/css; charset=utf-8" if name.endswith(".css")
                         else "application/javascript; charset=utf-8")
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ctype)
            else:
                self._send(404, b'{"ok":false,"error":"not found"}')
        elif path in ("/", "/index.html", "/studio", "/about"):
            # 单页应用：前端路由统一回 index.html；未构建时退回旧版单页
            built = os.path.join(DIST, "index.html")
            fp = built if os.path.exists(built) else os.path.join(WEB, "index.html")
            with open(fp, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif path in ("/exploded", "/exploded.html"):
            fp = os.path.join(WEB, "exploded.html")
            if not os.path.exists(fp):
                self._send(404, b'{"ok":false,"error":"not found"}')
            else:
                with open(fp, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
        elif path == "/sample/part.png":
            fp = os.path.join(ROOT, "data", "samples", "sample_part.png")
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    self._send(200, f.read(), "image/png")
            else:
                self._send(404, b'{"ok":false,"error":"sample missing"}')
        elif path.startswith("/vendor/"):
            name = os.path.basename(urllib.parse.unquote(path[8:]))
            fp = os.path.join(WEB, "vendor", name)
            if os.path.exists(fp) and name.endswith(".js"):
                with open(fp, "rb") as f:
                    self._send(200, f.read(), "application/javascript; charset=utf-8")
            else:
                self._send(404, b'{"ok":false,"error":"not found"}')
        elif path == "/api/scene":
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            def g(k, d=None):
                return q.get(k, [d])[0]
            try:
                fov = g("fov", "15x12").replace("×", "x").split("x")
                fw, fh = float(fov[0]), float(fov[1])
                data = build_scene(
                    task=g("task", "表面划痕"),
                    accuracy=float(g("accuracy", "0.03")),
                    fov_w=fw, fov_h=fh,
                    wd=float(g("wd", "160")),
                    speed=float(g("speed", "0")),
                    scan=g("scan", "area"),
                    moving=(g("moving", "0") in ("1", "true")),
                )
                self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]},
                                           ensure_ascii=False).encode("utf-8"))
        elif path == "/api/drawing-sample":
            try:
                if not os.path.exists(SAMPLE_DRAWING):
                    raise FileNotFoundError("示例图纸不存在")
                with open(SAMPLE_DRAWING, encoding="utf-8") as f:
                    out = drawing_result(f.read())
                out["sample"] = "合成样例 · 连接器壳体（非真实产品图）"
                self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send(500, json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]},
                                           ensure_ascii=False).encode("utf-8"))
        elif path == "/api/version":
            self._send(200, json.dumps({"version": __version__}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/tasks":
            self._send(200, json.dumps({"tasks": TASKS}, ensure_ascii=False).encode())
        elif path.startswith("/out/"):
            name = os.path.basename(urllib.parse.unquote(path[5:]))
            fp = os.path.join(OUT, name)
            if os.path.exists(fp) and name.endswith((".html", ".xml")):
                ctype = "text/html; charset=utf-8" if name.endswith(".html") else "text/plain; charset=utf-8"
                with open(fp, "rb") as f:
                    self._send(200, f.read(), ctype)
            else:
                self._send(404, b'{"ok":false,"error":"not found"}')
        else:
            self._send(404, b'{"ok":false,"error":"not found"}')

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/drawing":
            self._handle_drawing()
            return
        if path != "/api/spec":
            self._send(404, b'{"ok":false,"error":"not found"}')
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = compute(payload)
            body = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self._send(200, body)
        except Exception as e:  # 现场宁可报错也不要静默挂掉
            msg = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]},
                             ensure_ascii=False).encode("utf-8")
            self._send(500, msg)

    def _handle_drawing(self):
        """图纸 → 检测需求。上传 PDF 或 txt，返回推出来的视野、精度、任务。"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if payload.get("text"):
                text = payload["text"]
            elif payload.get("pdf"):
                text = read_drawing_pdf(payload["pdf"])
            else:
                raise ValueError("没有收到图纸内容")
            out = drawing_result(text)
            self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            msg = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]},
                             ensure_ascii=False).encode("utf-8")
            self._send(500, msg)


def port_busy(port: int) -> bool:
    """Windows 的 SO_REUSEADDR 允许同一端口被重复绑定，
    结果两个实例共享请求，改完代码也看不到变化。启动前先探一次。"""
    import socket as _s
    sk = _s.socket()
    sk.settimeout(0.5)
    try:
        return sk.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sk.close()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8848
    if port_busy(port):
        print("=" * 58)
        print(f"  端口 {port} 已被占用，可能已有一个实例在运行。")
        print("  直接再启动会出现两个进程抢同一端口，页面可能加载到旧代码。")
        print(f"  先关掉旧窗口，或执行： taskkill /F /PID <占用进程>")
        print("=" * 58)
        sys.exit(1)
    os.makedirs(OUT, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 58)
    print(f"  机器视觉成像方案生成器 · 演示界面 {__version__}")
    print(f"  {url}")
    print("  按 Ctrl+C 停止")
    print("=" * 58)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
