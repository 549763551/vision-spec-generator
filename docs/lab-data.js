/* ─────────────────────────────────────────────────────────────
   光学实验室 · 静态数据层
   GitHub Pages 是纯静态托管，没有 Python 后端，因此把
   core/scene.py::build_lab() 的计算逻辑原样搬到这里。
   返回值逐字段与服务端 /api/lab 一致，前端 fetchLab() 直接调用即可，
   页面交互（换灯型、改视野、改工作距离）与本地版完全相同。
   ───────────────────────────────────────────────────────────── */
(function (global) {
  'use strict';

  // 与 core/scene.py::LAB_LIGHTS / FORM_SHAPE / LAB_MOUNT 保持同步
  var LAB_LIGHTS = {
    RS:   ['环形光', 78],
    '2BS':['条形光', 78],
    HFS:  ['面光源', 90],
    PHFS: ['平行面光源', 90],
    CO:   ['同轴光', 90],
    DS:   ['圆顶光', 90],
    LPG:  ['线光源', 78],
    TUG:  ['隧道光', 90]
  };
  var FORM_SHAPE = {
    RS:'ring', '2BS':'bars', HFS:'panel', PHFS:'panel',
    CO:'coax', DS:'dome', LPG:'line', TUG:'tunnel'
  };
  var LAB_MOUNT = {
    RS:   { h:80,  h_range:[40,200], tiltable:true  },
    '2BS':{ h:70,  h_range:[40,200], tiltable:true  },
    HFS:  { h:110, h_range:[50,220], tiltable:false },
    PHFS: { h:110, h_range:[50,220], tiltable:false },
    CO:   { h:0,   h_range:[0,0],    tiltable:false },
    DS:   { h:26,  h_range:[14,70],  tiltable:false },
    LPG:  { h:80,  h_range:[40,200], tiltable:true  },
    TUG:  { h:30,  h_range:[16,70],  tiltable:false }
  };

  var VERSION = 'v0.6.4';

  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
  function r3(v) { return Math.round(v * 1000) / 1000; }
  function r2(v) { return Math.round(v * 100) / 100; }

  // 对应 core/scene.py::_light_geometry
  function lightGeometry(shape, fovW, scan, form, series, angle) {
    if (scan === 'line') shape = 'line';
    var scale = r3(clamp(fovW / 22.0, 0.55, 1.35));
    var geo = {
      shape: shape,
      scale: scale,
      name: form,
      series: series,
      angle: angle ? angle + '°' : '',
      color: '白光',
      direction: '',
      field: ''
    };
    if (shape === 'ring') {
      geo.radius = r3(clamp(0.42 + fovW / 34.0, 0.52, 1.02));
      geo.count = 28;
    } else if (shape === 'bars') {
      geo.length = r3(clamp(fovW / 26.0, 0.9, 1.9));
      geo.count = 2;
    } else if (shape === 'panel') {
      geo.radius = r3(clamp(0.50 + fovW / 30.0, 0.58, 1.15));
      geo.count = 0;
    } else if (shape === 'coax') {
      geo.radius = 0.34;
      geo.count = 0;
    } else if (shape === 'dome') {
      geo.radius = r3(clamp(0.40 + fovW / 40.0, 0.50, 0.86));
      geo.count = 0;
    } else if (shape === 'line') {
      geo.length = r3(clamp(fovW / 20.0, 1.1, 2.0));
      geo.count = 0;
    } else {
      geo.radius = 0.6;
      geo.count = 0;
    }
    return geo;
  }

  // 对应 core/scene.py::build_lab
  function buildLab(series, fovW, fovH, scan, wd) {
    if (!Object.prototype.hasOwnProperty.call(LAB_LIGHTS, series)) series = 'RS';
    fovW = Number(fovW) || 15;
    fovH = Number(fovH) || 12;
    wd = Number(wd) > 0 ? Number(wd) : 160;
    scan = scan || 'area';

    var form = LAB_LIGHTS[series][0];
    var defAngle = LAB_LIGHTS[series][1];
    var geo = lightGeometry(FORM_SHAPE[series], fovW, scan, form, series, defAngle);

    var base = LAB_MOUNT[series];
    var mount = { h: base.h, h_range: base.h_range.slice(), tiltable: base.tiltable, tilt: defAngle };

    var fovDeg = 2 * Math.atan((fovW / 2.0) / wd) * 180 / Math.PI;
    var lights = Object.keys(LAB_LIGHTS).map(function (s) {
      return {
        series: s,
        form: LAB_LIGHTS[s][0],
        h: LAB_MOUNT[s].h,
        tiltable: LAB_MOUNT[s].tiltable
      };
    });

    return {
      ok: true,
      series: series,
      form: form,
      default_angle: defAngle,
      fov: [fovW, fovH],
      wd: wd,
      mount: mount,
      camera: { wd: wd, fov_deg: r2(fovDeg), mount: 'bracket' },
      light: geo,
      lights: lights
    };
  }

  global.LabData = { buildLab: buildLab, version: VERSION };
})(window);
