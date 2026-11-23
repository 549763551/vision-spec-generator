/* 面阵光学试验台厂商参考数据。
 * 仅记录公开可核验项目；模型参数为结构示意，不代表真实机械尺寸。
 */
(function (global) {
  'use strict';

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
      dimensions: '尺寸字段冲突（待厂商确认）',
      usage: '3D、线扫与面阵光学实验。',
      features: [
        '厂商页面列出的适用范围包含 3D、线扫及面阵光学实验',
        '原页面“产品尺寸”行填“铝合金”，“产品材质”行填“900mm×800mm×1400mm”；字段与内容对应关系冲突，暂不采信具体尺寸'
      ],
      note: '公开页面未提供运动轴行程、控制器通道、负载和重复定位精度。',
      source: 'https://www.bmtmv.com/guangxue-peijian/34.html',
      verified: false,
      visual: { w: 9.0, d: 8.0, frame: 'single' }
    },
    {
      id: 'bmt-jc1918', vendor: 'BMT', model: 'BMT-JC1918-CCD',
      dimensions: '尺寸字段冲突（待厂商确认）',
      usage: '面阵光学实验。',
      features: [
        '厂商页面标注适用于面阵光学实验',
        '原页面“产品尺寸”行填“铝合金”，“产品材质”行填“700mm×700mm×1270mm”；字段与内容对应关系冲突，暂不采信具体尺寸'
      ],
      note: '公开页面未提供 XYZ 行程、相机夹持范围、控制器参数及负载。',
      source: 'https://www.bmtmv.com/guangxue-peijian/34.html',
      verified: false,
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

  global.BenchCatalog = { getBenches: getBenches };
})(window);
