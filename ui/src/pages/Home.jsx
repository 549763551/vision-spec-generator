import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowRight, Boxes, FileText, ScanLine, ShieldCheck } from 'lucide-react'
import { Chip } from '../components/ui'

const fade = {
  hidden: { opacity: 0, y: 10 },
  show: (i) => ({ opacity: 1, y: 0, transition: { delay: 0.04 * i, duration: 0.36, ease: [0.22, 1, 0.36, 1] } }),
}

const steps = [
  { icon: FileText, k: '01', t: '输入', d: '产品图纸或一张样张，加三行检测要求' },
  { icon: ScanLine, k: '02', t: '推算', d: '相机、镜头、光源、控制器四组联动计算' },
  { icon: ShieldCheck, k: '03', t: '自检', d: '代回公式复算，冲突当场报出来' },
  { icon: Boxes, k: '04', t: '落地', d: '方案书、流程指导书、四平台节点对照' },
]

const facts = [
  { v: '4', u: '组', l: '相机 / 镜头 / 光源 / 控制器' },
  { v: '29', u: '个', l: '回归用例，全部可手工验算' },
  { v: '4', u: '个', l: '视觉平台的节点命名对照' },
]

export default function Home() {
  return (
    <div className="mx-auto max-w-[1240px] px-5 sm:px-7">
      {/* ── 首屏 ───────────────────────────────────────────── */}
      <section className="grid items-start gap-12 pt-16 pb-14 sm:pt-24 sm:pb-20 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.85fr)] lg:gap-16">
        <div>
        <motion.div variants={fade} initial="hidden" animate="show" custom={0}>
          <Chip tone="accent">AI 机器视觉 · 答辩作品</Chip>
        </motion.div>

        <motion.h1
          variants={fade}
          initial="hidden"
          animate="show"
          custom={1}
          className="mt-6 max-w-[19ch] text-[34px] leading-[1.18] sm:text-[46px] sm:leading-[1.12]"
        >
          把选型从填表算数，
          <br />
          变成<span className="text-accent">看图说话</span>。
        </motion.h1>

        <motion.p
          variants={fade}
          initial="hidden"
          animate="show"
          custom={2}
          className="mt-6 max-w-[52ch] text-[14px] leading-[1.75] text-ink-3"
        >
          输入一份图纸或一张样张，输出相机、镜头、光源、控制器四组方案。每一步都带计算式，
          结论能被人拿计算器复核——这是它和「凭经验试」的区别。
        </motion.p>

        <motion.div
          variants={fade}
          initial="hidden"
          animate="show"
          custom={3}
          className="mt-9 flex flex-wrap items-center gap-3"
        >
          <Link
            to="/studio"
            className="inline-flex h-11 items-center gap-2 rounded-[9px] bg-accent px-5 text-[13.5px] font-medium text-[#08221f] transition hover:brightness-108"
          >
            进入工作台
            <ArrowRight size={15} strokeWidth={2.1} />
          </Link>
          <a
            href="/exploded"
            className="inline-flex h-11 items-center gap-2 rounded-[9px] border border-line px-5 text-[13.5px] text-ink-2 transition hover:border-line-2 hover:bg-surface-2 hover:text-ink-1"
          >
            看 3D 拆解
          </a>
        </motion.div>

        <motion.div
          variants={fade}
          initial="hidden"
          animate="show"
          custom={4}
          className="mt-12 grid grid-cols-1 gap-px overflow-hidden rounded-[12px] border border-line bg-line sm:grid-cols-3"
        >
          {facts.map((f) => (
            <div key={f.l} className="bg-bg px-4 py-4">
              <div className="text-[24px] font-medium leading-none tracking-[-0.02em] text-ink-1 tnum">
                {f.v}
                <span className="ml-0.5 text-[12px] font-normal text-ink-3">{f.u}</span>
              </div>
              <div className="mt-2 text-[11px] leading-snug text-ink-3">{f.l}</div>
            </div>
          ))}
        </motion.div>
        </div>

        <motion.div
          variants={fade}
          initial="hidden"
          animate="show"
          custom={3}
          className="lg:pt-10"
        >
          <SampleCard />
        </motion.div>
      </section>

      {/* ── 四步 ───────────────────────────────────────────── */}
      <section className="border-t border-line py-14">
        <h2 className="text-[10.5px] uppercase tracking-[0.11em] text-ink-3">怎么走完一次</h2>
        <div className="mt-7 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-6">
          {steps.map((s) => (
            <div key={s.k} className="relative">
              <div className="flex items-center gap-2.5">
                <s.icon size={16} strokeWidth={1.7} className="text-accent" />
                <span className="text-[10.5px] tracking-[0.08em] text-ink-3 tnum">{s.k}</span>
              </div>
              <h3 className="mt-3 text-[14px] text-ink-1">{s.t}</h3>
              <p className="mt-1.5 text-[11.5px] leading-relaxed text-ink-3">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 两个入口 ───────────────────────────────────────── */}
      <section className="grid grid-cols-1 gap-4 border-t border-line py-14 lg:grid-cols-2">
        <Entry
          to="/studio"
          eyebrow="工作台"
          title="方案生成器"
          desc="拖入图纸或样张，出四组参数、自检结论和可打印方案书。"
          tags={['图纸反推', '自检复算', '参数清单']}
        />
        <Entry
          href="/exploded"
          eyebrow="可视化"
          title="3D 拆解视图"
          desc="机台随参数变形：面阵换线阵、环光换背光，四层结构逐层拆开。"
          tags={['数据驱动', '逐层拆解', '流程节点']}
        />
      </section>
    </div>
  )
}

const SAMPLE = [
  ['相机', '2 MP', '1600 × 1200 · 1/1.8"'],
  ['镜头', '75 mm', 'WD 160 mm · C 口'],
  ['光源', 'RS 30°', '环形光 · 暗场 · 白光'],
  ['控制器', 'APS', '24 V · 4 通道'],
]

function SampleCard() {
  return (
    <div className="rounded-[14px] border border-line bg-surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="text-[10.5px] uppercase tracking-[0.1em] text-ink-3">示例输出</span>
        <span className="text-[10.5px] text-ink-3 tnum">15×12 mm · 0.03 mm</span>
      </div>
      <div className="divide-y divide-line">
        {SAMPLE.map(([k, v, d]) => (
          <div key={k} className="flex items-baseline gap-3 px-4 py-3">
            <span className="w-12 shrink-0 text-[11px] text-ink-3">{k}</span>
            <span className="text-[14px] font-medium text-ink-1 tnum">{v}</span>
            <span className="ml-auto text-right text-[11px] leading-snug text-ink-3 tnum">{d}</span>
          </div>
        ))}
      </div>
      <div className="border-t border-line px-4 py-3">
        <Link to="/studio" className="group inline-flex items-center gap-1.5 text-[11.5px] text-ink-3 transition-colors hover:text-accent">
          换成你自己的参数
          <ArrowRight size={12} className="transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </div>
  )
}

function Entry({ to, href, eyebrow, title, desc, tags }) {
  const Cmp = to ? Link : 'a'
  const props = to ? { to } : { href }
  return (
    <Cmp
      {...props}
      className="group relative flex flex-col rounded-[14px] border border-line bg-surface p-6 transition-colors hover:border-line-2 hover:bg-surface-2"
    >
      <span className="text-[10.5px] uppercase tracking-[0.1em] text-ink-3">{eyebrow}</span>
      <h3 className="mt-2 flex items-center gap-2 text-[17px]">
        {title}
        <ArrowRight
          size={15}
          className="text-ink-3 transition-all group-hover:translate-x-0.5 group-hover:text-accent"
        />
      </h3>
      <p className="mt-2 max-w-[42ch] text-[12px] leading-relaxed text-ink-3">{desc}</p>
      <div className="mt-5 flex flex-wrap gap-1.5">
        {tags.map((t) => (
          <span key={t} className="rounded-[5px] border border-line px-2 py-0.5 text-[10.5px] text-ink-3">
            {t}
          </span>
        ))}
      </div>
    </Cmp>
  )
}
