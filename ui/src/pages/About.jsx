import { Chip } from '../components/ui'

const rows = [
  ['像素精度', '精度 = 视野 ÷ 分辨率', '尺寸链基本关系'],
  ['需求分辨率', '视野 ÷ 精度，再按缺陷占 3~4 像素放大', '按精度反推，再按可检性放大'],
  ['曝光上限', 't ≤ 精度 ÷ 运动速度', '拖影约束'],
  ['行频', '行频 = 运动速度 ÷ 像素精度', '线阵纵向采样约束'],
  ['焦距', 'f / WD = Sensor / FOV（长边配长边）', '相似三角形'],
  ['景深', '2·N·c·(1+β)/β²，c 取 2 倍像元', '近摄近似'],
  ['成像判据', '特征/背景灰度差 ≥ 30、不过曝、不失焦', '工程经验阈值'],
]

const fails = [
  ['不控制物理光源', '只输出该用什么光源。可编程控制器缺失时，闭环无从谈起。'],
  ['只认有文字层的 PDF', '扫描件要 OCR，这次没做；解析失败会直接报错，不猜。'],
  ['公差语义靠关键词', '能抓出 26 条公差，但哪条约束哪个尺寸判不了，所以输出带置信度。'],
  ['线阵只做了横向', '纵向密度由行频定，卷帘/拼接等工程细节没覆盖。'],
  ['平台节点名是通用对应', '不是各家官方命名手册，版本差异需现场核对。'],
]

const iter = [
  ['砍掉教室人数统计', '原计划和本方案并行，后来砍掉。', '它和这套选型方法没有交集，两个都做等于两个半成品。'],
  ['清晰度指标换算法', '最初用相邻像素差分均值，三张清晰度差很远的图都得 2~3 分。', '换成拉普拉斯方差，做了模糊对照组：原图 290 / σ1.5 得 61 / σ3 得 14。阈值是这样定的。'],
  ['精度推算去重', '把「公差带÷5」当最小特征传给相机，相机又乘 3 像素——同一约束乘两次。', '改完后像素精度 0.0093，与一个已落地项目实测 0.0088 相差 6%。'],
  ['3D 由计算驱动', '第一版模型是画死的，换参数不动。', '改为按选型结果生成几何：面阵换线阵机身变长条，环光换背光变平板。'],
]

export default function About() {
  return (
    <div className="soft-in mx-auto max-w-[1240px] px-5 pt-14 pb-6 sm:px-7">
      <div className="max-w-[820px]">
      <Chip tone="accent">方法与边界</Chip>
      <h1 className="mt-5 text-[28px] leading-tight sm:text-[34px]">
        每个数字都要能被人拿计算器复核
      </h1>
      <p className="mt-5 max-w-[62ch] text-[13.5px] leading-[1.8] text-ink-3">
        这套工具的立场很简单：不给「最佳方案」这种无法验证的结论，只给能追到依据的推算过程。
        公式来自通行做法，程序负责选、解、验算三件事，不假装是自己推导的。
      </p>

      <section className="mt-14">
        <h2 className="text-[10.5px] uppercase tracking-[0.11em] text-ink-3">计算依据</h2>
        <div className="mt-4 overflow-hidden rounded-[12px] border border-line">
          <table className="w-full border-collapse text-[12px]">
            <thead>
              <tr>
                {['量', '关系式', '依据'].map((h, i) => (
                  <th key={h} className="border-b border-line bg-surface-2 px-3 py-2 text-left text-[10px] font-medium uppercase tracking-[0.07em] text-ink-3"
                    style={{ width: i === 0 ? '18%' : i === 2 ? '24%' : undefined }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r[0]} className="transition-colors hover:bg-surface-2/60">
                  <td className="border-b border-line/60 px-3 py-2 text-ink-3">{r[0]}</td>
                  <td className="border-b border-line/60 px-3 py-2 font-mono text-[11.5px] text-accent">{r[1]}</td>
                  <td className="border-b border-line/60 px-3 py-2 text-[11px] text-ink-3">{r[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-14">
        <h2 className="text-[10.5px] uppercase tracking-[0.11em] text-ink-3">它做不到什么</h2>
        <div className="mt-4 divide-y divide-line rounded-[12px] border border-line bg-surface">
          {fails.map(([t, d]) => (
            <div key={t} className="px-4 py-3.5">
              <div className="text-[12.5px] text-ink-1">{t}</div>
              <div className="mt-1 text-[11.5px] leading-relaxed text-ink-3">{d}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-14">
        <h2 className="text-[10.5px] uppercase tracking-[0.11em] text-ink-3">四次改动</h2>
        <div className="mt-4 space-y-3">
          {iter.map(([t, before, after]) => (
            <div key={t} className="rounded-[12px] border border-line bg-surface p-4">
              <div className="text-[12.5px] text-ink-1">{t}</div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                <div className="rounded-[8px] bg-surface-2 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.08em] text-ink-3">改之前</div>
                  <div className="mt-1 text-[11.5px] leading-relaxed text-ink-3">{before}</div>
                </div>
                <div className="rounded-[8px] border border-accent/25 bg-accent-soft/40 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.08em] text-accent/80">改之后</div>
                  <div className="mt-1 text-[11.5px] leading-relaxed text-ink-2">{after}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
      </div>
    </div>
  )
}
