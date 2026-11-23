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

  // 厂商公开页面中的面阵实验平台。仅录入可核验信息；缺失字段不做推测。
  var BENCHES = [
    {
      id: 'cst-fatb650', vendor: 'CST', model: 'CST-FATB650-HJY',
      dimensions: '930 × 800 × 1045 mm',
      usage: '通用面阵光学实验、成像方案与光源测试。',
      features: [
        '实验平台集成相机供电与光源控制器',
        '上银丝杆与导轨；相机支持上下、左右、前后微调及垂直角度调节',
        '集成 8 通道模拟控制器与 2 通道恒流控制器，可驱动 24 V / 5 V 光源',
        '提供外置相机触发输入/输出接口，配置 6-pin 相机电源线与网线',
        '配备 2 个光源固定架与 2 个简易相机固定架'
      ],
      note: '一体化面阵实验平台。公开页面未给出各轴有效行程及重复定位精度。',
      source: 'https://www.cstmv.com/show/1800.html',
      verified: true,
      visual: { w: 8.6, d: 9.2, frame: 'single' }
    },
    {
      id: 'cst-large-fov', vendor: 'CST', model: 'CST-PTF300200-SYS',
      dimensions: '整机占地未公开；连接杆高度 1500 mm',
      usage: '面阵相机大视野检测，便于架设大尺寸面光源与长条光源。',
      features: [
        '配备 4 个底座及 4 根高度 1500 mm 的连接杆',
        '相机固定架支持上下、前后及角度调节',
        '配备 4 个光源固定支架，支持条形光及开孔面光的高度、角度调节'
      ],
      note: '厂商未公布底座间距、整机占地、最大负载及各轴行程；三维视图仅示意四立柱结构。',
      source: 'https://www.cstmv.com/show/1800.html',
      verified: true,
      visual: { w: 10.0, d: 9.0, frame: 'four-post' }
    },
    {
      id: 'cst-portable', vendor: 'CST', model: 'CST-PTF340200',
      dimensions: '340 × 200 × 376 mm',
      usage: '现场出差调试、展会演示与小型面阵光学实验。',
      features: [
        '两根高度可调不锈钢支柱，分别安装相机与光源',
        '两根支柱分别具有三个运动自由度，可调高度并在平面内移动',
        '内置 4 通道数字控制器，亮度 0–255 级调节',
        '支持 RS232 串口远程控制；结构可拆卸，便于携带'
      ],
      note: '便携型平台；公开页面未公布各方向有效行程及支架负载。',
      source: 'https://www.cstmv.com/show/1800.html',
      verified: true,
      visual: { w: 6.8, d: 5.6, frame: 'portable' }
    },
    {
      id: 'bmt-jc1903', vendor: 'BMT', model: 'BMT-JC1903',
      dimensions: '900 × 800 × 1400 mm（原页面表格字段错位，采购前复核）',
      usage: '3D、线扫与面阵光学实验。',
      features: [
        '厂商页面列出的适用范围包含 3D、线扫及面阵光学实验',
        '页面同时列出铝合金材质信息；型号、尺寸与材质需以正式规格书再次核对'
      ],
      note: '公开页面未提供运动轴行程、控制器通道、负载和重复定位精度。',
      source: 'https://www.bmtmv.com/guangxue-peijian/34.html',
      verified: true,
      visual: { w: 9.0, d: 8.0, frame: 'single' }
    },
    {
      id: 'bmt-jc1918', vendor: 'BMT', model: 'BMT-JC1918-CCD',
      dimensions: '700 × 700 × 1270 mm（原页面表格字段错位，采购前复核）',
      usage: '面阵光学实验。',
      features: [
        '厂商页面标注适用于面阵光学实验',
        '页面同时列出铝合金材质信息；尺寸与材质字段顺序需以正式规格书再次核对'
      ],
      note: '公开页面未提供 XYZ 行程、相机夹持范围、控制器参数及负载。',
      source: 'https://www.bmtmv.com/guangxue-peijian/34.html',
      verified: true,
      visual: { w: 7.0, d: 7.0, frame: 'single' }
    },
    {
      id: 'lots-area-frame', vendor: 'LOTS', model: '面阵实验架（型号待核）',
      dimensions: '官方产品页参数暂未核验',
      usage: '机器视觉面阵实验架；结构与规格需以厂商图纸或正式规格书确认。',
      features: [
        '保留用户提供的 LOTS 产品页作为资料核对入口',
        '当前未将未读取到的尺寸、调节行程、负载与控制器参数写入选型条件'
      ],
      note: '本次未能读取到该页面的可核验参数；取得产品 PDF、图纸或实物测量数据后再补全。',
      source: 'https://www.lotsmv.com/productview/744.html',
      verified: false,
      visual: { w: 8.6, d: 9.2, frame: 'single' }
    }
  ];

  function getBenches() {
    return BENCHES.map(function (item) {
      return {
        id: item.id, vendor: item.vendor, model: item.model,
        dimensions: item.dimensions, usage: item.usage,
        features: item.features.slice(), note: item.note,
        source: item.source, verified: item.verified,
        visual: { w: item.visual.w, d: item.visual.d, frame: item.visual.frame }
      };
    });
  }

  var VERSION = 'v0.6.5';

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

  global.LabData = { buildLab: buildLab, getBenches: getBenches, version: VERSION };
})(window);
