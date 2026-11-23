"""场景规格：把选型结果翻译成 3D 场景参数。

三维页面的模型不是画死的。每一层的形状、尺寸、发光元件数量都来自
camera / lens / light / controller 四个模块的真实计算结果：

  环光 → 圆环 + 灯珠阵列     背光 → 平板发光面
  同轴 → 45° 半透半反立方体  圆顶 → 半球腔
  条形 → 两侧长条            线光 → 一条长条（配线阵）
  面阵 → 方机身              线阵 → 细长条形机身
  FA  → 短镜筒              远心 → 长镜筒 + 大前组
"""
from __future__ import annotations

import math

from .camera import select_camera, select_line_camera, task_requires_color
from .lens import select_lens
from .light import recommend_light
from .controller import select_controller
from .procedure import CHAINS


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# 光源系列 → 三维形态
FORM_SHAPE = {
    "RS": "ring", "2BS": "bars", "HFS": "panel", "PHFS": "panel",
    "CO": "coax", "DS": "dome", "LPG": "line", "TUG": "tunnel",
}

# 光学实验室可选光源：系列 → (显示名, 默认发光角度°)
# 角度只是初始值，实验室里由用户拖动实时改；空串表示该形态不谈发光角。
LAB_LIGHTS = {
    "RS":   ("环形光", 30),
    "2BS":  ("条形光", 30),
    "HFS":  ("面光源", 90),
    "PHFS": ("平行面光源", 90),
    "CO":   ("同轴光", 0),
    "DS":   ("圆顶光", 0),
    "LPG":  ("线光源", 45),
    "TUG":  ("隧道光", 0),
}


def build_lab(series: str = "RS", fov_w: float = 15.0, fov_h: float = 12.0,
              scan: str = "area") -> dict:
    """光学实验室：直接指定光源系列，返回该形态的 3D 几何。

    与 build_scene 的区别：build_scene 从 task 反推"该用什么光源"（推荐）；
    这里反过来——用户自由换光源形态，在推荐基础上手动调试。
    发光角与工作距离由前端在 3D 里实时调整，不必每次回后端。
    """
    from .light import LightSpec

    if series not in LAB_LIGHTS:
        series = "RS"
    form, def_angle = LAB_LIGHTS[series]
    light = LightSpec(
        direction="", field_type="", color="白光",
        size_mm=(round(fov_w * 1.2, 1), round(fov_h * 1.2, 1)),
        polarization=False, form=form, series=series,
        angle=(f"{def_angle}°" if def_angle else ""),
    )
    geo = _light_geometry(light, fov_w, scan)
    return {
        "ok": True,
        "series": series,
        "form": form,
        "default_angle": def_angle,
        "fov": [fov_w, fov_h],
        "light": geo,
        "lights": [{"series": s, "form": f} for s, (f, _a) in LAB_LIGHTS.items()],
    }


def _cam_geometry(cam):
    """相机机身：面阵是方箱，线阵是细长条；分辨率越高机身越大一点。"""
    if cam.scan == "line":
        return {"shape": "bar", "size": [2.02, 0.34, 0.44], "mount_d": 0.30}
    s = _clamp(0.80 + cam.megapixel / 30.0, 0.80, 1.30)
    return {"shape": "box", "size": [1.14 * s, 0.60 * s, 0.94 * s], "mount_d": 0.20}


def _lens_geometry(lens, cam, tele):
    """镜头：FA 短筒，远心长筒大前组，线阵长筒粗身。"""
    if cam.scan == "line":
        return {"kind": "line", "len": 0.86, "d": 0.33, "front": 0.36,
                "name": "线阵镜头", "sub": f"M42 口 · 放大倍率 {cam.sensor_w / (cam.sensor_w * 1.0):.2f}"}
    if tele:
        return {"kind": "tele", "len": 0.88, "d": 0.30, "front": 0.38,
                "name": "远心镜头", "sub": "按倍率选型，倍率固定"}
    f = lens.f_recommend
    return {"kind": "fa", "len": _clamp(0.34 + f / 260.0, 0.42, 0.82),
            "d": _clamp(0.24 + f / 900.0, 0.26, 0.34), "front": 0.30,
            "name": "定焦镜头", "sub": f"{f:g} mm · WD {lens.wd_at_recommend:.0f} mm · C 口"}


def _light_geometry(light, fov_w, scan):
    """光源：形态由系列代码决定，尺寸由视野决定。"""
    shape = FORM_SHAPE.get(light.series, "ring")
    if scan == "line":
        shape = "line"
    scale = _clamp(fov_w / 22.0, 0.55, 1.35)
    geo = {"shape": shape, "scale": round(scale, 3),
           "name": light.form or light.direction,
           "series": light.series, "angle": light.angle,
           "color": light.color, "direction": light.direction,
           "field": light.field_type}
    if shape == "ring":
        geo["radius"] = round(_clamp(0.42 + fov_w / 34.0, 0.52, 1.02), 3)
        geo["count"] = 28
    elif shape == "bars":
        geo["length"] = round(_clamp(fov_w / 26.0, 0.9, 1.9), 3)
        geo["count"] = 2
    elif shape == "panel":
        geo["radius"] = round(_clamp(0.5 + fov_w / 30.0, 0.58, 1.15), 3)
        geo["count"] = 0
    elif shape == "coax":
        geo["radius"] = 0.34
        geo["count"] = 0
    elif shape == "dome":
        geo["radius"] = round(_clamp(0.40 + fov_w / 40.0, 0.5, 0.86), 3)
        geo["count"] = 0
    elif shape == "line":
        geo["length"] = round(_clamp(fov_w / 20.0, 1.1, 2.0), 3)
        geo["count"] = 0
    else:
        geo["radius"] = 0.6
        geo["count"] = 0
    return geo


def build_scene(task: str, accuracy: float, fov_w: float, fov_h: float,
                wd: float = 200.0, speed: float = 0.0, scan: str = "area",
                moving: bool = False, height_var: float = 0.0) -> dict:
    """返回三维场景所需的全部数据（几何 + 文案 + 参数表）。"""

    if scan == "line":
        cam = select_line_camera(fov_w=fov_w, accuracy=accuracy, speed=speed)
        moving = True
    else:
        cam = select_camera(fov_w=fov_w, fov_h=fov_h, accuracy=accuracy,
                            moving=moving, speed=speed,
                            need_color=task_requires_color(task))

    tele = (task in ("尺寸测量", "轮廓定位") and scan == "area")
    if scan == "line":
        lens = None
    else:
        lens = select_lens(sensor_w=cam.sensor_w, sensor_h=cam.sensor_h,
                           fov_w=fov_w, fov_h=fov_h, wd=wd,
                           pixel_um=cam.pixel_um,
                           need_precision_measure=(task in ("尺寸测量", "轮廓定位")),
                           height_variation=height_var)

    light = recommend_light(task=task, fov_w=fov_w, fov_h=fov_h)
    if scan == "line":
        light.series = "LPG"
        light.form = "线光源" if light.direction != "背光" else "线背光"
        light.angle = ""

    channels = 4 if scan == "line" else 4
    ctrl = select_controller(light_channels=channels, channel_power_w=12.0,
                             need_program_control=moving,
                             exposure_max_us=cam.exposure_max_us,
                             need_time_sequence=moving)

    cam_geo = _cam_geometry(cam)
    lens_geo = _lens_geometry(lens, cam, tele) if lens else _lens_geometry(None, cam, False)
    light_geo = _light_geometry(light, fov_w, scan)

    # ---- 四个部件的标注与参数表 ----
    if cam.scan == "line":
        cam_rows = [
            ["横向像素", f"{cam.width_px}", "扫描宽度 ÷ 精度，再按缺陷占 3 像素放大"],
            ["像素精度", f"{cam.pixel_accuracy_mm:.4f} mm/px", "扫描宽度 ÷ 横向像素数，纵向靠行频对齐"],
            ["行频", (f"{cam.line_rate_hz:.0f} Hz" if cam.line_rate_hz else "—"),
             "速度 ÷ 像素精度；行频偏低会把圆拉成椭圆"],
            ["单行曝光", (f"≤ {cam.exposure_max_us:.0f} μs" if cam.exposure_max_us else "—"),
             "1 ÷ 行频，超了纵向拖影"],
            ["数据率", (f"{cam.data_rate_mbps:.0f} MB/s" if cam.data_rate_mbps else "—"),
             "像素数 × 行频 × 位深，决定接口等级"],
            ["接口", cam.interface.split("（")[0], "线阵高行频基本都要 Camera Link / CXP"],
        ]
        cam_sub = f"{cam.width_px} px · {cam.sensor_name} · {cam.interface.split('（')[0]}"
    else:
        cam_rows = [
            ["分辨率", f"{cam.width_px} × {cam.height_px}", "视野 ÷ 精度，再按缺陷占 3 像素放大"],
            ["像素精度", f"{cam.pixel_accuracy_mm:.4f} mm/px", "视野宽 ÷ 像素数，所有像素判据的换算基准"],
            ["靶面", cam.sensor_name, "决定焦距与镜头的搭配余量"],
            ["色彩", cam.color_mode, "尺寸与缺陷用黑白，灵敏度更高"],
            ["快门", cam.shutter.split("（")[0], "运动拍摄必须全局曝光"],
            ["接口", cam.interface.split("（")[0], "带宽与线长的权衡"],
        ]
        cam_sub = f"{cam.width_px}×{cam.height_px} · {cam.sensor_name} · {cam.interface.split('（')[0]}"

    lens_rows = [
        ["类型", lens_geo["name"], "精密测量用远心，缺陷与有无判断用 FA"],
        ["焦距", ("—（按倍率）" if tele else (f"{lens.f_recommend:g} mm" if lens else "—")),
         "f / WD = Sensor / FOV，长边配长边"],
        ["工作距离", (f"{lens.wd_at_recommend:.0f} mm" if lens else "现场定"),
         "由焦距与视野反推，机身装配以此为准"],
        ["景深", (f"{lens.dof_estimate_mm:.2f} mm" if lens else "—"),
         "近摄近似，高度变化超过就要重算"],
        ["接口", ("M42 / F 口" if cam.scan == "line" else "C 口"), "法兰距与像面覆盖范围"],
    ]
    if lens:
        lens_sub = ("远心 · 按倍率选型" if tele
                    else f"{lens.f_recommend:g} mm · WD {lens.wd_at_recommend:.0f} mm · C 口")
    else:
        lens_sub = "M42 口 · 线阵专用"

    light_rows = [
        ["形态", light.form or light.direction, "形态决定光路，方向只是结果"],
        ["型号代码", light.series, "按系列选具体型号与发光面尺寸"],
        ["发光角", (light.angle or "—"), "环形光 90° 直下打，30° 贴表面斜打"],
        ["场型", light.field_type, "亮场看反射，暗场看散射"],
        ["颜色", light.color, "白光保通用；单色可换对比度"],
        ["发光面", f"{light.size_mm[0]:g} × {light.size_mm[1]:g} mm", "比视野大 20%，边缘照度才不塌"],
    ]
    light_sub = f"{light.series} {light.angle + ' · ' if light.angle else ''}{light.direction} · {light.color}"

    ctrl_rows = [
        ["系列", ctrl.series, "模拟 / 数字 / 频闪，按是否需要程序控光选"],
        ["通道数", f"{ctrl.channels} 路", "光源分区数量，通道不够就得多台"],
        ["供电", f"{ctrl.voltage} V / {ctrl.power_w} W", "光源功率 × 1.2 余量"],
        ["通讯", ("串口 + 网口" if ctrl.has_ethernet else ("串口" if ctrl.has_serial else "无（手调）")),
         "要程序改亮度才需要"],
        ["频闪", ("支持" if ctrl.has_boost else "不支持"),
         "飞拍靠频闪压曝光，常亮补不亮"],
    ]
    ctrl_sub = f"{ctrl.series} · {ctrl.voltage}V · {ctrl.power_w}W · {ctrl.channels} 通道"

    mode = "线阵机台" if cam.scan == "line" else "面阵机台"
    preset = f"{task} · {light.series} {'线光' if cam.scan == 'line' else (light.form or '')} · {mode}"

    notes = []
    if cam.scan == "line":
        notes.append(
            "线阵靠运动扫出第二维：横向像素由视野和精度定，纵向密度由行频定。"
            "行频不对，圆会变成椭圆——这是线阵最常见的翻车点。"
        )
    notes.append(
        "四组计算是联动的：改一个参数，下游全变。"
        f"当前光源给 {light.series}，控制器要 {ctrl.channels} 通道，都是算出来的。"
    )
    if light.polarization:
        notes.append("本方案需要偏振：高反光件的镜面反射会盖掉特征。")

    return {
        "ok": True,
        "preset": preset,
        "scan": cam.scan,
        "mode": mode,
        "inputs": {"task": task, "accuracy": accuracy, "fov": [fov_w, fov_h],
                   "wd": wd, "speed": speed, "moving": bool(moving)},
        "flow": list(CHAINS.get(task, CHAINS["表面划痕"])),
        "geometry": {"cam": cam_geo, "lens": lens_geo, "light": light_geo},
        "labels": [
            {"id": "cam", "name": cam_geo.get("shape") == "bar" and "线阵相机" or "工业相机", "sub": cam_sub},
            {"id": "lens", "name": lens_geo["name"], "sub": lens_sub},
            {"id": "light", "name": (light.form or light.direction), "sub": light_sub},
            {"id": "ctrl", "name": "光源控制器", "sub": ctrl_sub},
        ],
        "panels": {
            "cam": {"name": cam_geo.get("shape") == "bar" and "线阵相机" or "工业相机",
                    "sub": cam_sub, "rows": cam_rows},
            "lens": {"name": lens_geo["name"], "sub": lens_sub, "rows": lens_rows},
            "light": {"name": (light.form or light.direction), "sub": light_sub, "rows": light_rows},
            "ctrl": {"name": "光源控制器", "sub": ctrl_sub, "rows": ctrl_rows},
        },
        "notes": notes,
        "steps": {"cam": cam.steps, "light": light.steps, "ctrl": ctrl.steps,
                  "lens": (lens.steps if lens else [])},
    }
