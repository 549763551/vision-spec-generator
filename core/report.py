"""把选型结果渲染成一份可打印的 HTML 方案书。

为什么是 HTML 而不是 GUI：
  零依赖、双击即看、可直接 Ctrl+P 存 PDF 交作业，
  答辩现场不需要装任何界面框架。
"""

import html
import datetime

CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 24px 64px;
  background: #12141a; color: #e6e8ee;
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 14px; line-height: 1.7;
}
.wrap { max-width: 920px; margin: 0 auto; }
header { border-bottom: 1px solid #2b303c; padding-bottom: 20px; margin-bottom: 28px; }
h1 { font-size: 24px; font-weight: 600; margin: 0 0 6px; letter-spacing: .5px; }
.sub { color: #8b93a5; font-size: 13px; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px;
  background: #1e2634; color: #4da3ff; font-size: 12px; margin-left: 8px; }
h2 { font-size: 15px; font-weight: 600; margin: 32px 0 12px;
  padding-left: 10px; border-left: 3px solid #4da3ff; color: #cfd6e4; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card { background: #1a1d25; border: 1px solid #2b303c; border-radius: 8px; padding: 14px 16px; }
.card .k { font-size: 12px; color: #8b93a5; margin-bottom: 8px; }
.card .v { font-size: 18px; font-weight: 600; color: #e6e8ee; }
.card .n { font-size: 12px; color: #8b93a5; margin-top: 6px; }
.metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 8px; }
.metric { background: #1a1d25; border: 1px solid #2b303c; border-radius: 8px; padding: 12px 14px; }
.metric .k { font-size: 12px; color: #8b93a5; }
.metric .v { font-size: 20px; font-weight: 600; margin-top: 4px; }
.ok { color: #3ddc84; } .warn { color: #ffb020; } .bad { color: #ff5252; }
ol { margin: 8px 0 0; padding-left: 22px; color: #b9c1d1; }
ol li { margin: 4px 0; font-size: 13px; }
table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #2b303c; vertical-align: top; }
th { color: #8b93a5; font-weight: 500; font-size: 12px; }
td.rule { color: #79839a; font-size: 12px; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.pill.pass { background: #12301f; color: #3ddc84; }
.pill.warn { background: #33270c; color: #ffb020; }
.pill.fail { background: #331416; color: #ff5252; }
.risk { background: #1a1d25; border: 1px solid #4a3a12; border-radius: 8px; padding: 14px 18px; }
.risk li { color: #e8c98a; }
.fix { background: #1a1d25; border: 1px solid #123a5a; border-radius: 8px; padding: 14px 18px; }
.fix li { color: #7fb8ff; }
.fix b { color: #a8cdf5; }
.note { color: #79839a; font-size: 12px; margin-top: 6px; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #2b303c;
  color: #6b7280; font-size: 12px; }
@media print {
  body { background: #fff; color: #111; padding: 0; }
  .card, .metric, .risk { background: #fafafa; border-color: #ddd; }
  h1, .card .v, .metric .v { color: #111; }
  .sub, .card .k, .metric .k, .note, footer { color: #555; }
  h2 { color: #111; }
  th { color: #555; } td { border-color: #ddd; } ol, td.rule { color: #444; }
}
"""


def _e(x) -> str:
    return html.escape(str(x))


def _steps(items) -> str:
    if not items:
        return "<p class='note'>无</p>"
    return "<ol>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ol>"


def _checks(rep) -> str:
    rows = []
    for c in rep.checks:
        rows.append(
            f"<tr><td>{_e(c.name)}</td>"
            f"<td><span class='pill {c.status}'>{ {'pass': '通过', 'warn': '警告', 'fail': '不通过'}[c.status] }</span></td>"
            f"<td>{_e(c.detail)}</td><td class='rule'>{_e(c.rule)}</td></tr>"
        )
    return (
        "<table><tr><th>检查项</th><th>结论</th><th>实测 / 复算</th><th>依据</th></tr>"
        + "".join(rows) + "</table>"
    )


def _remedies(rep) -> str:
    """修复方向：对警告 / 不通过项反解出的可执行修法（含数字）。"""
    items = [(c, r) for c in rep.checks for r in c.remedies]
    if not items:
        return ""
    lis = []
    for c, r in items:
        lis.append(f"<li><b>{_e(c.name)}</b>：{_e(r)}</li>")
    return (
        "<h2>修复方向</h2><div class='fix'><ul style='margin:0;padding-left:20px'>"
        + "".join(lis) + "</ul></div>"
    )


def _multi_shot_note(cam) -> str:
    if not cam.fov_shot:
        return ""
    return (
        f"<p class='sub' style='color:#7fb8ff'>超规格拆分：单相机无法覆盖该视野与精度组合，"
        f"已按 <b>{cam.shots_w}×{cam.shots_h} = {cam.shots_w * cam.shots_h} 幅</b>多拍方案选型"
        f"（单幅视野 {cam.fov_shot[0]:.2f}×{cam.fov_shot[1]:.2f} mm，"
        f"机械位移逐幅拍摄或多相机分区）；镜头 / 光源 / 自检均按单幅视野计算。</p>"
    )


def build_html(inputs: dict, diag, cam, lens, light, ctrl, val, version="v0.1.0") -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # 输入摘要
    fov_w, fov_h = inputs["fov"]
    in_rows = [
        ("检测任务", inputs["task"]),
        ("目标精度", f"{inputs['accuracy']:g} mm"),
        ("视野", f"{fov_w:g} × {fov_h:g} mm"),
        ("期望工作距离", f"{inputs['wd']:g} mm"),
        ("拍摄方式", ("运动拍摄，速度 " + f"{inputs['speed']:g} mm/s") if inputs["moving"] else "静止拍摄"),
        ("色彩需求", "需要颜色判别" if inputs["need_color"] else "仅判尺寸/缺陷"),
        ("颜色目标", f"突出 {inputs['boost_color']}" if inputs["boost_color"]
                    else (f"压掉 {inputs['suppress_color']}" if inputs["suppress_color"] else "未指定")),
        ("被测物高度变化", f"{inputs['height_var']:g} mm" if inputs["height_var"] else "未提供"),
    ]
    in_html = "".join(
        f"<tr><td style='color:#8b93a5;width:140px'>{_e(k)}</td><td>{_e(v)}</td></tr>"
        for k, v in in_rows
    )

    # 图像诊断
    if diag is None:
        diag_html = ("<p class='note'>本次运行未提供样张，跳过图像诊断。"
                     "方案仅基于输入参数推算，未经图像验证。</p>")
    else:
        gc = "ok" if diag.gray_diff >= 30 else ("warn" if diag.gray_diff >= 20 else "bad")
        oc = "bad" if diag.overexposed_ratio > 0.05 else ("warn" if diag.overexposed_ratio > 0.01 else "ok")
        ec = "bad" if (diag.lap_var < 15 and diag.strong_edge_ratio < 0.002) else "ok"
        gcls = {"合格": "ok", "临界": "warn", "不合格": "bad"}[diag.grade]
        issues = ("<ul style='margin:8px 0 0;padding-left:20px;color:#e8a5a5'>"
                  + "".join(f"<li>{_e(i)}</li>" for i in diag.issues) + "</ul>") if diag.issues else ""
        notes = ("<ul style='margin:8px 0 0;padding-left:20px;color:#8b93a5'>"
                 + "".join(f"<li>{_e(i)}</li>" for i in diag.notes) + "</ul>") if diag.notes else ""
        diag_html = f"""
        <div class="metrics">
          <div class="metric"><div class="k">特征/背景灰度差（判据 ≥ 30）</div>
            <div class="v {gc}">{diag.gray_diff:.1f}</div></div>
          <div class="metric"><div class="k">过曝像素占比</div>
            <div class="v {oc}">{diag.overexposed_ratio:.2%}</div></div>
          <div class="metric"><div class="k">清晰度（拉普拉斯方差）</div>
            <div class="v {ec}">{diag.lap_var:.0f}</div></div>
        </div>
        <p class="sub">图像 {diag.width}×{diag.height}，灰度均值 {diag.mean:.1f}，
          标准差 {diag.std:.1f}，Otsu 阈值 {diag.otsu_threshold}；
          综合判定 <span class="{gcls}">{diag.grade}</span></p>
        {issues}
        {notes}
        <p class="note">判据出处：「什么才算一张好图」——灰度差 ≥ 30、整体均匀、不能过曝。
          本次判级阈值来源：{_e(diag.threshold_source)}。</p>
        """

    # 四组计算过程
    calc_html = f"""
    <h2>相机：{cam.megapixel:g} MP / {cam.color_mode} / {_e(cam.shutter)}</h2>
    {_multi_shot_note(cam)}
    {_steps(cam.steps)}
    <h2>镜头：{lens.f_recommend:g} mm / 工作距离 {lens.wd_at_recommend:.0f} mm</h2>
    {_steps(lens.steps)}
    <h2>光源：{_e(light.form or light.direction)}　{_e(light.series)}{(' ' + light.angle) if light.angle else ''}　·　{_e(light.field_type)}　·　{_e(light.color)}</h2>
    {_steps(light.steps)}
    <h2>控制器：{_e(ctrl.series_full)}（{_e(ctrl.model_string)}）</h2>
    {_steps(ctrl.steps)}
    """

    # 风险与边界
    all_warn = []
    for name, obj in (("相机", cam), ("镜头", lens), ("光源", light), ("控制器", ctrl)):
        for w in getattr(obj, "warnings", []):
            all_warn.append(f"[{name}] {w}")
    if diag is not None:
        for i in diag.issues:
            all_warn.append(f"[图像] {i}")
    risk_html = ("<div class='risk'><ul style='margin:0;padding-left:20px'>"
                 + "".join(f"<li>{_e(w)}</li>" for w in all_warn) +
                 "</ul></div>") if all_warn else "<p class='note'>本次推算未触发风险项。</p>"

    overall_cls = {"通过": "ok", "有警告": "warn", "不通过": "bad"}[val.overall]

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>成像方案书 · {_e(inputs['task'])}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>机器视觉成像方案书 <span class="tag">{_e(version)}</span></h1>
  <div class="sub">生成时间 {now}　|　输入：{_e(inputs['task'])}，
    精度 {inputs['accuracy']:g} mm，视野 {fov_w:g}×{fov_h:g} mm
    　|　自检结论 <span class="{overall_cls}">{val.overall}</span></div>
</header>

<h2>方案摘要</h2>
<div class="cards">
  <div class="card"><div class="k">相机</div>
    <div class="v">{cam.megapixel:g} MP</div>
    <div class="n">{cam.width_px}×{cam.height_px}　{cam.sensor_name}　{cam.color_mode}<br>
      {_e(cam.interface)}　{_e(cam.mount)}{f'<br>多拍 {cam.shots_w}×{cam.shots_h} 幅（单幅 {cam.fov_shot[0]:.2f}×{cam.fov_shot[1]:.2f} mm）' if cam.fov_shot else ''}</div></div>
  <div class="card"><div class="k">镜头</div>
    <div class="v">{lens.f_recommend:g} mm</div>
    <div class="n">WD {lens.wd_at_recommend:.0f} mm　视场角 {lens.fov_angle_deg:.1f}°　{lens.magnification:.2f}×</div></div>
  <div class="card"><div class="k">光源</div>
    <div class="v">{_e(light.form or light.direction)}</div>
    <div class="n">型号代码 {_e(light.series)}{('　' + light.angle) if light.angle else ''}　{_e(light.direction)}<br>
      {_e(light.field_type)}　{_e(light.color)}　发光面 {light.size_mm[0]:g}×{light.size_mm[1]:g} mm</div></div>
  <div class="card"><div class="k">控制器</div>
    <div class="v">{_e(ctrl.series)}</div>
    <div class="n">{ctrl.voltage}V / {ctrl.power_w}W / {ctrl.channels} 通道</div></div>
</div>

<h2>输入条件</h2>
<table>{in_html}</table>

<h2>图像质量诊断</h2>
{diag_html}

<h2>计算过程（可逐步复算）</h2>
{calc_html}

<h2>自检复算</h2>
{_checks(val)}
{_remedies(val)}

<h2>风险与边界</h2>
{risk_html}

<footer>
  本方案由规则引擎按固定公式推算，公式出处已在每步标注通行做法页码。<br>
  边界：不含光学仿真、不含实拍验证；光源仅为方案建议，不控制物理光源。
  实际采购前须以厂商样本核对分辨率档位、靶面尺寸与接口。<br>
  版本 {_e(version)}　|　生成器：vision-spec-generator
</footer>
</div></body></html>"""
