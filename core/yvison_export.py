"""把选型结果导出成 Yvison 的相机参数模板。

依据实际文件：F:\\Yvisionn\\Yvison\\Config\\Parameter\\User_Camera.xml
  该文件内容其实是 JSON（扩展名是 .xml），结构为：
    [ { "UserCameras": [ {自定义名称, 实际名称, Type, Value, Enum} ], "Name": 品牌 } , ... ]
  已确认可写的字段（海康组）：Width / Height / PixelFormat /
  ExposureTime / ExposureAuto / Gain / GainAuto / TriggerMode / TriggerSource。
  注意 " Gain" 的实际名称带前导空格，是原始数据的写法，匹配时必须 strip。

安全约定：
  1. 只生成副本，绝不覆盖 Config 目录下的原文件（该目录已有 .bak 备份，说明改坏过）。
  2. 无法确定的字段不写（例如非飞拍场景不给 ExposureTime，彩色相机的 PixelFormat 不动）。
  3. 每个改动都返回 旧值 → 新值，便于人工核对后再替换。
"""

import json
import os


# 各字段取值来源。返回 None 表示本次不修改该字段。
def _value_for(field: str, cam, moving: bool):
    if field == "Width":
        return cam.width_px
    if field == "Height":
        return cam.height_px
    if field == "ExposureTime":
        # 只有飞拍场景才有"曝光上限"这个约束；静止拍摄时曝光由亮度决定，不预设
        return int(round(cam.exposure_max_us)) if cam.exposure_max_us else None
    if field == "Gain":
        # 通行做法：增益是无脑放大，一般不用，放 0
        return 0
    if field == "GainAuto":
        return "Off"
    if field == "ExposureAuto":
        return "Off"
    if field == "TriggerMode":
        return "On" if moving else "Off"
    if field == "TriggerSource":
        return "Line0" if moving else "Software"
    if field == "PixelFormat":
        # 黑白相机给 Mono8；彩色不擅自动（Bayer 排序因厂商而异，写错会跑不起来）
        return "Mono8" if cam.color_mode == "黑白" else None
    return None


def build_camera_template(cam, src_path: str, moving: bool = False,
                          brand: str = "海康"):
    """读取模板，按选型结果填值，返回 (新数据, 改动清单, 错误信息)。"""
    if not os.path.exists(src_path):
        return None, [], f"模板文件不存在：{src_path}"

    try:
        with open(src_path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, [], f"模板不是合法 JSON：{e}"

    if not isinstance(data, list):
        return None, [], "模板结构不是预期的列表，可能不是 User_Camera 文件"

    group = next((g for g in data if g.get("Name") == brand), None)
    if group is None:
        names = [g.get("Name") for g in data if isinstance(g, dict)]
        return None, [], f"模板里没有品牌「{brand}」，现有：{names}"

    changes = []
    for item in group.get("UserCameras", []):
        real = str(item.get("实际名称", "")).strip()   # " Gain" → "Gain"
        new = _value_for(real, cam, moving)
        if new is None:
            continue
        old = item.get("Value", "")
        if str(old) == str(new):
            continue
        item["Value"] = str(new)
        changes.append((real, old, new))

    return data, changes, ""


def save_template(data, out_path: str) -> str:
    """保存副本，保持与原文件一致的 CRLF 换行与无 BOM 编码。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\r\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return out_path
