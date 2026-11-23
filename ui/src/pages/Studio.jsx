import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Aperture, Camera, CircuitBoard, Download, ExternalLink,
  Info, Lightbulb, Play, RotateCcw, Upload,
} from 'lucide-react'
import { Button, Chip, Empty, ErrorBox, Field, Loading, Panel, Table, Td, inputCls } from '../components/ui'

const PRESETS = [
  { k: 'p1', label: '小视野精测', task: '表面划痕', accuracy: 0.01, fov_w: 12, fov_h: 10, wd: 130, moving: false, speed: 0 },
  { k: 'p2', label: '字符识别', task: '平面字符', accuracy: 0.05, fov_w: 40, fov_h: 33, wd: 300, moving: false, speed: 0 },
  { k: 'p3', label: '飞拍', task: '表面划痕', accuracy: 0.02, fov_w: 30, fov_h: 20, wd: 200, moving: true, speed: 200 },
  { k: 'p4', label: '曲面瓶盖字符', task: '平面字符', surface: '曲面', accuracy: 0.05, fov_w: 30, fov_h: 30, wd: 180, moving: false, speed: 0 },
]

const EMPTY_FORM = {
  task: '表面划痕', surface: '平整', accuracy: 0.03, fov_w: 15, fov_h: 12, wd: 160,
  moving: false, speed: 200, height_var: 0, channels: 2, channel_power: 10, program: false,
}

const STATUS = {
  pass: { label: '通过', tone: 'ok' },
  warn: { label: '警告', tone: 'warn' },
  fail: { label: '不通过', tone: 'fail' },
}

/* 3D 页是整页跳转，返回时 React 会重新挂载，组件 state 全部归零。
   把工作台会话存 sessionStorage，让样张、参数、结果都跟着回来。 */
const SESSION_KEY = 'visionspec.studio.session'

function readSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null') || null
  } catch {
    return null
  }
}

function writeSession(s) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(s))
  } catch {
    /* 图片 dataUrl 过大时，退而保存参数与结果，至少不让整页回到默认值 */
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...s, img: null }))
    } catch { /* 隐私模式等：放弃持久化，不影响主流程 */ }
  }
}

export default function Studio() {
  const restored = useMemo(readSession, [])
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, ...(restored?.form || {}) }))
  const [tasks, setTasks] = useState([])
  const [preset, setPreset] = useState(restored?.preset || '')
  const [data, setData] = useState(restored?.data || null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [drawNote, setDrawNote] = useState(restored?.drawNote || '')
  const [drawing, setDrawing] = useState(false)
  const [img, setImg] = useState(restored?.img || null)   /* {dataUrl, name, size} */
  const fileRef = useRef(null)

  useEffect(() => {
    writeSession({ form, preset, data, drawNote, img })
  }, [form, preset, data, drawNote, img])

  useEffect(() => {
    const qs = new URLSearchParams(location.search)
    if (qs.get('sample') === '1') {
      setForm(EMPTY_FORM)
      setImg({ dataUrl: '/sample/part.png', name: '内置合成样张', sample: true })
      run(EMPTY_FORM, null, true)
      return
    }
    const q = qs.get('preset')
    const hit = PRESETS.find((p) => p.k === q)
    if (hit) {
      const next = { ...EMPTY_FORM, task: hit.task, surface: hit.surface || EMPTY_FORM.surface, accuracy: hit.accuracy, fov_w: hit.fov_w, fov_h: hit.fov_h, wd: hit.wd, moving: hit.moving, speed: hit.speed }
      setForm(next)
      setPreset(hit.k)
      run(next)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    fetch('/api/tasks')
      .then((r) => r.json())
      .then((d) => setTasks(d.tasks || []))
      .catch(() => setTasks([]))
  }, [])

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  async function run(override, imageArg, useSample = false) {
    const image = imageArg === undefined ? (img ? img.dataUrl : null) : imageArg
    const payload = { ...form, ...override, image, use_sample: useSample }
    setBusy(true)
    setErr('')
    try {
      const r = await fetch('/api/spec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const d = await r.json()
      if (!d.ok) throw new Error(d.error || '服务端返回异常')
      setData(d)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  function applyPreset(p) {
    const next = { ...form, task: p.task, surface: p.surface || form.surface, accuracy: p.accuracy, fov_w: p.fov_w, fov_h: p.fov_h, wd: p.wd, moving: p.moving, speed: p.speed }
    setForm(next)
    setPreset(p.k)
    run(next)
  }

  const IMG_RE = /^image\/(jpeg|jpg|png|bmp|webp|tiff)$|\.(jpe?g|png|bmp|webp|tiff?)$/i

  async function onFile(file) {
    if (!file) return
    if (IMG_RE.test(file.type || '') || IMG_RE.test(file.name)) return loadImage(file)
    return onDrawing(file)
  }

  async function loadImage(file) {
    setDrawing(true)
    setDrawNote('')
    try {
      const dataUrl = await new Promise((res, rej) => {
        const fr = new FileReader()
        fr.onload = () => res(fr.result)
        fr.onerror = () => rej(new Error('读取文件失败'))
        fr.readAsDataURL(file)
      })
      const next = { dataUrl, name: file.name, size: file.size }
      setImg(next)
      setPreset('')
      /* 图片只喂给成像诊断；视野与精度仍取当前参数，不会被图片改写 */
      await run(null, dataUrl)
    } catch (e) {
      setErr('样张读取失败：' + e.message)
    } finally {
      setDrawing(false)
    }
  }

  async function onDrawing(file) {
    if (!file) return
    setDrawing(true)
    setDrawNote('')
    try {
      const buf = await file.arrayBuffer()
      let body
      if (/\.pdf$/i.test(file.name)) {
        const bytes = new Uint8Array(buf)
        let bin = ''
        for (let i = 0; i < bytes.length; i += 8192) {
          bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192))
        }
        body = { pdf: 'data:application/pdf;base64,' + btoa(bin) }
      } else {
        body = { text: new TextDecoder('utf-8').decode(buf) }
      }
      const r = await fetch('/api/drawing', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const d = await r.json()
      if (!d.ok) throw new Error(d.error || '解析失败')
      const next = { ...form, task: d.task, accuracy: d.accuracy, fov_w: d.fov_w, fov_h: d.fov_h }
      setForm(next)
      setPreset('')
      setDrawNote(`图纸反推　视野 ${d.fov_w}×${d.fov_h} · 精度 ${d.accuracy} · ${d.task} · 置信度${d.confidence}`)
      run(next)
    } catch (e) {
      setErr('图纸解析失败：' + e.message)
    } finally {
      setDrawing(false)
    }
  }

  const exportHref = useMemo(() => {
    if (!data) return '/exploded'
    const q = new URLSearchParams({
      task: form.task, accuracy: String(form.accuracy),
      fov: `${form.fov_w}x${form.fov_h}`, wd: String(form.wd),
      ...(form.moving ? { speed: String(form.speed) } : {}),
    })
    return '/exploded?' + q.toString()
  }, [data, form])

  return (
    <div className="mx-auto max-w-[1240px] px-5 pt-8 pb-4 sm:px-7">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[22px]">方案工作台</h1>
          <p className="mt-1 text-[12px] text-ink-3">
            图纸或参数进去，四组结论和自检出来。改动任何一项，下游全部重算。
          </p>
        </div>
        <a href={exportHref} className="text-[12px] text-ink-3 transition-colors hover:text-accent">
          在 3D 中查看这台机台 →
        </a>
      </header>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[356px_minmax(0,1fr)]">
        {/* ── 输入 ─────────────────────────────────────── */}
        <div className="lg:sticky lg:top-[74px] lg:self-start">
          <Panel title="输入" bodyClass="p-4 space-y-4">
            <Dropzone
              busy={drawing}
              note={drawNote}
              img={img}
              onPick={() => fileRef.current?.click()}
              onFile={onFile}
              onClear={() => { setImg(null); run(null, null) }}
            />
            <button
              onClick={() => {
                setPreset('')
                setImg({ dataUrl: '/sample/part.png', name: '内置合成样张', sample: true })
                run(null, null, true)
              }}
              className="interactive block w-full text-left text-[11px] text-ink-3 hover:text-accent"
            >
              没有样张？用内置合成样张 →
            </button>
            <input
              ref={fileRef} type="file"
              accept=".pdf,.txt,.jpg,.jpeg,.png,.bmp,.webp,.tif,.tiff,image/*"
              className="hidden"
              onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = '' }}
            />

            <div>
              <span className="mb-1.5 block text-[11px] text-ink-3">常用场景</span>
              <div className="flex flex-wrap gap-1.5">
                {PRESETS.map((p) => (
                  <button
                    key={p.k}
                    onClick={() => applyPreset(p)}
                    className={`rounded-[6px] border px-2 py-1 text-[11px] transition-colors ${
                      preset === p.k
                        ? 'border-accent/45 bg-accent-soft text-accent'
                        : 'border-line text-ink-3 hover:border-line-2 hover:text-ink-1'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <Field label="检测任务" htmlFor="task">
              <select id="task" className={inputCls} value={form.task} onChange={(e) => set({ task: e.target.value })}>
                {(tasks.length ? tasks : [form.task]).map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>

            <Field label="工件表面" htmlFor="surface" hint="决定高角度是否改低角度">
              <select id="surface" className={inputCls} value={form.surface} onChange={(e) => set({ surface: e.target.value })}>
                {['平整', '曲面', '高反光', '镜面'].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </Field>

            <div className="grid grid-cols-2 gap-2.5">
              <Field label="精度" hint="mm" htmlFor="acc">
                <input id="acc" type="number" step="0.001" className={inputCls}
                  value={form.accuracy} onChange={(e) => set({ accuracy: parseFloat(e.target.value) || 0 })} />
              </Field>
              <Field label="工作距离" hint="mm" htmlFor="wd">
                <input id="wd" type="number" step="10" className={inputCls}
                  value={form.wd} onChange={(e) => set({ wd: parseFloat(e.target.value) || 0 })} />
              </Field>
              <Field label="视野 宽" hint="mm" htmlFor="fw">
                <input id="fw" type="number" className={inputCls}
                  value={form.fov_w} onChange={(e) => set({ fov_w: parseFloat(e.target.value) || 0 })} />
              </Field>
              <Field label="视野 高" hint="mm" htmlFor="fh">
                <input id="fh" type="number" className={inputCls}
                  value={form.fov_h} onChange={(e) => set({ fov_h: parseFloat(e.target.value) || 0 })} />
              </Field>
            </div>

            <label className="flex cursor-pointer items-center gap-2 text-[12px] text-ink-2 select-none">
              <input type="checkbox" checked={form.moving} onChange={(e) => set({ moving: e.target.checked })}
                className="h-3.5 w-3.5 accent-[#2fd3c5]" />
              运动拍摄（飞拍）
            </label>
            {form.moving && (
              <Field label="运动速度" hint="mm/s" htmlFor="spd">
                <input id="spd" type="number" step="10" className={inputCls}
                  value={form.speed} onChange={(e) => set({ speed: parseFloat(e.target.value) || 0 })} />
              </Field>
            )}

            <Button variant="primary" size="lg" icon={Play} busy={busy} onClick={() => run()} className="w-full">
              {busy ? '推算中' : '生成方案'}
            </Button>
          </Panel>
        </div>

        {/* ── 结果 ─────────────────────────────────────── */}
        <div className="min-w-0 space-y-5">
          {err && <ErrorBox message={err} onRetry={() => run()} />}

          {busy && !data && (
            <Panel bodyClass="p-0"><Loading label="正在按参数推算四组结果…" /></Panel>
          )}

          {!busy && !data && !err && (
            <Panel bodyClass="p-0">
              <Empty
                icon={Camera}
                title="还没有方案"
                desc="填好左侧参数点「生成方案」，或直接把产品图纸拖进来。"
              />
            </Panel>
          )}

          {data && (
            <div className="rise-in space-y-5">
              <Results data={data} form={form} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ── 图纸投放 ─────────────────────────────────────────────────── */
function Dropzone({ busy, note, img, onPick, onFile, onClear }) {
  const [over, setOver] = useState(false)
  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={onPick}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onPick()}
        onDragOver={(e) => { e.preventDefault(); setOver(true) }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); onFile(e.dataTransfer.files?.[0]) }}
        className={`flex cursor-pointer flex-col items-center rounded-[10px] border border-dashed px-3 py-4 text-center transition-colors ${
          over ? 'border-accent bg-accent-soft' : 'border-line-2 bg-surface-2/40 hover:border-accent/60'
        }`}
      >
        {img ? (
          <>
            <img
              src={img.dataUrl} alt="样张预览"
              className="max-h-[86px] w-auto rounded-[6px] border border-line object-contain"
            />
            <span className="mt-2 max-w-full truncate text-[11.5px] text-ink-2">{img.name}</span>
            <button
              onClick={(e) => { e.stopPropagation(); onClear() }}
              className="interactive mt-1 text-[11px] text-ink-3 underline underline-offset-2 hover:text-fail"
            >
              移除样张
            </button>
          </>
        ) : (
          <>
            <Upload size={15} strokeWidth={1.7} className={busy ? 'animate-pulse text-accent' : 'text-ink-3'} />
            <span className="mt-2 text-[12px] text-ink-2">{busy ? '正在处理…' : '拖入图纸或样张'}</span>
            <span className="mt-0.5 text-[11px] text-ink-3">PDF / TXT 推参数　JPG / PNG 判成像</span>
          </>
        )}
      </div>
      {note && (
        <p className="mt-2 border-l-2 border-accent/50 pl-2.5 text-[11px] leading-relaxed text-ink-3">
          {note}
        </p>
      )}
    </div>
  )
}

/* ── 结果区 ───────────────────────────────────────────────────── */
function Results({ data, form }) {
  const { camera, lens, light, controller, validate, procedure, report_url } = data
  const need = camera.res_for_defect?.[0] || 0
  const cover = need ? Math.min(1, need / camera.w) : 0
  /* 带当前推荐光源进光学实验室。WD 是相机到工件的距离，不是光源安装高度，
     传过去会让灯具默认架太高、光直接打飞，所以只带光源系列与视野。 */
  const labHref = '/lab?' + new URLSearchParams({
    series: light?.series || 'RS',
    fov: `${form.fov_w}x${form.fov_h}`,
  }).toString()

  return (
    <>
      {data.diag && <DiagPanel diag={data.diag} />}
      {!data.diag && data.diag_error && <DiagPanel error={data.diag_error} />}
      {!data.diag && !data.diag_error && (
        <div className="interactive flex items-center gap-2.5 rounded-[10px] border border-line bg-surface px-3.5 py-2.5">
          <Info size={14} strokeWidth={1.8} className="shrink-0 text-ink-3" />
          <p className="text-[12px] leading-relaxed text-ink-3">
            未提供样张，本次跳过成像诊断——四组计算不依赖样张，结果照常有效。
          </p>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <SpecCard
          icon={Camera} label="相机" value={`${camera.mp} MP`} tone="accent"
          lines={[
            `${camera.w} × ${camera.h}　${camera.sensor}`,
            `${camera.accuracy.toFixed(4)} mm/px　${camera.color}`,
            `${(camera.interface || '').split('（')[0]}　${(camera.mount || '').split('（')[0]}`,
          ]}
          foot={need ? `需求 ${need} px　余量 ${(camera.w / need).toFixed(2)}×` : null}
          bar={cover}
        />
        <SpecCard
          icon={Aperture} label={lens.tele ? '镜头（建议远心）' : '镜头'} value={`${lens.f} mm`}
          lines={[
            `WD ${lens.wd} mm${lens.wd_alt ? `　备选 ${lens.wd_alt} mm` : ''}`,
            `视场角 ${lens.angle}°　倍率 ${lens.mag}×`,
            `景深 ≈ ${lens.dof} mm`,
          ]}
        />
        <SpecCard
          icon={Lightbulb} label="光源" value={light.form || light.direction}
          lines={[
            `${light.series}${light.angle ? '　' + light.angle : ''}　${light.direction}`,
            `${light.field}　${light.color}`,
            `发光面 ${light.size[0]} × ${light.size[1]} mm${light.polar ? '　需偏振' : ''}`,
          ]}
        />
        <SpecCard
          icon={CircuitBoard} label="控制器" value={controller.series}
          lines={[
            `${controller.v} V　${controller.p} W　${controller.ch} 通道`,
            controller.serial ? '支持串口' : '无通讯（手调）',
            controller.boost ? '支持频闪' : '不支持频闪',
          ]}
        />
      </div>

      <Panel
        title="自检复算"
        sub={`${validate.pass} 通过 · ${validate.warn} 警告 · ${validate.fail} 不通过`}
        actions={
          <Chip tone={validate.fail ? 'fail' : validate.warn ? 'warn' : 'ok'}>
            {validate.overall}
          </Chip>
        }
        bodyClass="p-0"
      >
        <Table head={[{ label: '检查项', width: '26%' }, { label: '结论', width: '12%' }, { label: '说明' }, { label: '依据', width: '24%' }]}>
          {validate.checks.map((c, i) => (
            <tr
              key={i}
              className={`transition-colors hover:bg-surface-2/60 ${
                c.status === 'fail' ? 'bg-fail/5' : c.status === 'warn' ? 'bg-warn/5' : ''
              }`}
            >
              <Td>{c.name}</Td>
              <Td>
                <Chip tone={STATUS[c.status].tone}>{STATUS[c.status].label}</Chip>
              </Td>
              <Td>{c.detail}</Td>
              <Td dim>{c.rule}</Td>
            </tr>
          ))}
        </Table>
      </Panel>

      <Panel
        title="流程作业指导书"
        sub={`${procedure.length} 个功能节点 · 参数带出处`}
        bodyClass="p-0"
      >
        <Table head={[{ label: '步', width: '6%' }, { label: '功能节点', width: '26%' }, { label: '参数' }, { label: '出处', width: '30%' }]}>
          {procedure.map((s) => (
            <tr key={s.no} className="transition-colors hover:bg-surface-2/60">
              <Td dim>{String(s.no).padStart(2, '0')}</Td>
              <Td className="text-ink-1">{s.node}</Td>
              <Td mono>
                {s.params.length
                  ? s.params.map((p, i) => (
                      <div key={i}>
                        <span className="text-ink-3">{p[0]} = </span>
                        {p[1]}
                      </div>
                    ))
                  : '—'}
              </Td>
              <Td dim>
                {s.params.map((p) => p[2]).filter(Boolean).map((t, i) => <div key={i}>{t}</div>)}
              </Td>
            </tr>
          ))}
        </Table>
      </Panel>

      <div className="flex flex-wrap items-center gap-2.5">
        <a
          href={report_url} target="_blank" rel="noreferrer"
          className="interactive pressable inline-flex h-9 items-center gap-2 rounded-[8px] bg-accent px-4 text-[13px] font-medium text-[#08221f] hover:bg-accent-hi hover:shadow-[0_2px_14px_-4px_#2fd3c580]"
        >
          <ExternalLink size={14} strokeWidth={2} />
          打开完整方案书
        </a>
        <Button icon={Lightbulb} onClick={() => window.open(labHref, '_blank')}>进光学实验室调试</Button>
        <Button icon={Download} onClick={() => downloadParams(data)}>导出参数清单</Button>
        <Button
          variant="ghost" icon={RotateCcw}
          onClick={() => {
            const q = new URLSearchParams({
              task: form.task, accuracy: String(form.accuracy),
              fov: `${form.fov_w}x${form.fov_h}`, wd: String(form.wd),
            })
            window.open('/exploded?' + q.toString(), '_blank')
          }}
        >
          在 3D 中查看
        </Button>
        <span className="ml-auto text-[11px] text-ink-3 tnum">
          {validate.fail > 0 ? '存在不通过项，装配前必须处理' : '可打印为 PDF 归档'}
        </span>
      </div>
    </>
  )
}

function DiagPanel({ diag, error }) {
  if (error) {
    return (
      <Panel title="成像诊断" actions={<Chip tone="warn">未完成</Chip>}>
        <p className="text-[12px] leading-relaxed text-ink-3">{error}</p>
        <p className="mt-2 text-[11px] text-ink-3/80">样张只影响这一块，四组计算不受影响。</p>
      </Panel>
    )
  }

  const tone = diag.grade === '合格' ? 'ok' : diag.grade === '临界' ? 'warn' : 'fail'
  const metrics = [
    ['灰度差', diag.gray_diff, '特征与背景，判据 ≥ 30'],
    ['过曝像素', `${diag.over}%`, '亮部细节是否丢失'],
    ['拉普拉斯方差', diag.lap, '清晰度，越高越锐'],
    ['强边占比', `${diag.edge}%`, '真实边缘密度'],
  ]

  return (
    <Panel
      title="成像诊断"
      sub={`样张 ${diag.w} × ${diag.h}　判据来自工程阈值，不是拍脑袋`}
      actions={<Chip tone={tone}>{diag.grade}</Chip>}
    >
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[10px] border border-line bg-line sm:grid-cols-4">
        {metrics.map(([k, v, d]) => (
          <div key={k} className="bg-surface px-3 py-2.5">
            <div className="text-[11px] text-ink-3">{k}</div>
            <div className="mt-1 text-[16px] font-medium leading-none text-ink-1 tnum">{v}</div>
            <div className="mt-1.5 text-[10.5px] leading-snug text-ink-3/80">{d}</div>
          </div>
        ))}
      </div>

      {diag.issues && diag.issues.length > 0 && (
        <ul className="mt-3 space-y-1">
          {diag.issues.map((t, i) => (
            <li key={i} className="flex gap-2 text-[11.5px] leading-relaxed text-[#ffb3a8]">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-fail" />
              {t}
            </li>
          ))}
        </ul>
      )}

      {diag.notes && diag.notes.length > 0 && (
        <ul className="mt-2 space-y-1">
          {diag.notes.map((t, i) => (
            <li key={i} className="text-[11.5px] leading-relaxed text-ink-3">{t}</li>
          ))}
        </ul>
      )}

      <p className="mt-3 border-t border-line pt-2.5 text-[11px] leading-relaxed text-ink-3/80">
        样张只能判断这张图够不够用，<b className="font-medium text-ink-3">推不出视野与精度</b>——
        图片里没有标定尺。那两项由图纸或人工给定。
      </p>
    </Panel>
  )
}

function SpecCard({ icon: Icon, label, value, lines = [], foot, bar }) {
  return (
    <div className="interactive rounded-[12px] border border-line bg-surface p-3.5 hover:border-line-2">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-[0.08em] text-ink-3">
        <Icon size={12} strokeWidth={1.8} className="text-accent" />
        {label}
      </div>
      <div className="mt-2 text-[19px] font-medium leading-tight tracking-[-0.01em] text-ink-1 tnum">
        {value}
      </div>
      <div className="mt-2 space-y-1">
        {lines.filter(Boolean).map((l, i) => (
          <div key={i} className="text-[11.5px] leading-relaxed text-ink-3 tnum">{l}</div>
        ))}
      </div>
      {typeof bar === 'number' && (
        <div className="mt-2.5">
          <div className="h-[3px] overflow-hidden rounded-full bg-surface-2">
            <div className="h-full rounded-full bg-accent/70" style={{ width: `${Math.round(bar * 100)}%` }} />
          </div>
        </div>
      )}
      {foot && <div className="mt-2 text-[11px] text-ink-3/80 tnum">{foot}</div>}
    </div>
  )
}

/* ── 参数清单导出 ─────────────────────────────────────────────── */
function downloadParams(d) {
  const c = d.camera, l = d.lens, li = d.light, ct = d.controller
  const out = {
    _说明: '相机参数对照清单。这不是任何视觉软件或相机 SDK 的工程文件，不能直接导入。字段名按 GenICam SFNC 命名，可照着在软件里逐项设置。',
    _核验: [
      '分辨率需 ≤ 相机最大分辨率，且满足 WidthInc / HeightInc 对齐（常见为 4 或 8 的倍数）',
      '曝光单位 μs；静止拍摄未给上限，需按现场亮度实测确定',
      '增益建议置 0，优先靠光强补亮，避免放大噪声',
      '触发方式与光源延时需与机台 PLC 时序一起核对',
    ],
    camera: {
      Width: c.w, Height: c.h,
      PixelFormat: c.color === '黑白' ? 'Mono8' : 'BayerRG8',
      ExposureTime: c.exposure ?? null, ExposureAuto: 'Off',
      Gain: 0, GainAuto: 'Off',
      TriggerMode: c.exposure ? 'On' : 'Off',
      TriggerSource: c.exposure ? 'Line0' : 'Software',
      _Interface: (c.interface || '').split('（')[0],
      _LensMount: (c.mount || '').split('（')[0],
    },
    lens: {
      FocalLength_mm: l.f, WorkingDistance_mm: l.wd,
      FieldOfViewAngle_deg: l.angle, DOF_estimate_mm: l.dof,
      Telecentric_recommended: l.tele, LensType_provided: l.tele ? '远心（建议）' : 'FA 定焦',
    },
    light: {
      Form: li.form, Series: li.series, Angle: li.angle || null,
      Direction: li.direction, FieldType: li.field, Color: li.color,
      EmittingArea_mm: li.size, Polarizer: li.polar,
    },
    controller: {
      Series: ct.series, Voltage_V: ct.v, Power_W: ct.p,
      Channels: ct.ch, Serial: ct.serial, Boost: ct.boost,
    },
    selfCheck: {
      Overall: d.validate.overall, Pass: d.validate.pass,
      Warn: d.validate.warn, Fail: d.validate.fail,
      Attention: d.validate.checks
        .filter((x) => x.status !== 'pass')
        .map((x) => ({ 项目: x.name, 结论: x.status === 'fail' ? '不通过' : '警告', 说明: x.detail })),
    },
  }
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'camera_params_' + new Date().toISOString().slice(0, 16).replace(/[:T-]/g, '') + '.json'
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 3000)
}
