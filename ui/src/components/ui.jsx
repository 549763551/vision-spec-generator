import { Loader2, AlertTriangle, Inbox } from 'lucide-react'

/* ── 按钮：三个变体，全局只有这三种 ───────────────────────────── */
export function Button({ variant = 'outline', size = 'md', busy, icon: Icon, children, className = '', ...rest }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-[8px] font-medium ' +
    'transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-55 select-none'
  const sizes = { sm: 'h-8 px-3 text-[12px]', md: 'h-9 px-4 text-[13px]', lg: 'h-11 px-5 text-[13.5px]' }
  const variants = {
    primary: 'bg-accent text-[#08221f] hover:brightness-108 active:brightness-95',
    outline: 'border border-line text-ink-2 hover:bg-surface-2 hover:border-line-2 hover:text-ink-1',
    ghost: 'text-ink-3 hover:text-ink-1 hover:bg-surface-2',
  }
  return (
    <button
      className={`${base} ${sizes[size]} ${variants[variant]} ${className}`}
      disabled={busy || rest.disabled}
      {...rest}
    >
      {busy ? <Loader2 size={14} className="animate-spin" /> : Icon ? <Icon size={14} strokeWidth={1.9} /> : null}
      {children}
    </button>
  )
}

/* ── 面板：标题 + 内容，全站唯一的容器形态 ─────────────────────── */
export function Panel({ title, sub, actions, children, className = '', bodyClass = '' }) {
  return (
    <section className={`rounded-[14px] border border-line bg-surface ${className}`}>
      {(title || actions) && (
        <header className="flex items-center gap-3 border-b border-line px-4 py-3">
          <div className="min-w-0 flex-1">
            {title && (
              <h2 className="text-[10.5px] font-medium uppercase tracking-[0.11em] text-ink-3">{title}</h2>
            )}
            {sub && <p className="mt-1 truncate text-[11.5px] text-ink-3">{sub}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={bodyClass || 'p-4'}>{children}</div>
    </section>
  )
}

/* ── 表单字段：label 与控件永远成对，保证可访问性 ─────────────── */
export function Field({ label, hint, htmlFor, children }) {
  return (
    <label htmlFor={htmlFor} className="block">
      <span className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-[11px] text-ink-3">{label}</span>
        {hint && <span className="text-[10.5px] text-ink-3/70 tnum">{hint}</span>}
      </span>
      {children}
    </label>
  )
}

export const inputCls =
  'h-9 w-full rounded-[8px] border border-line bg-surface-2 px-2.5 text-[13px] text-ink-1 tnum ' +
  'transition-colors duration-150 hover:border-line-2 focus:border-accent focus:outline-none'

/* ── 数字卡：值用等宽数字，避免切换时抖动 ─────────────────────── */
export function Stat({ label, value, sub, tone = 'default', className = '' }) {
  const toneCls = {
    default: 'text-ink-1',
    accent: 'text-accent',
    ok: 'text-ok',
    warn: 'text-warn',
    fail: 'text-fail',
  }[tone]
  return (
    <div className={`rounded-[10px] border border-line bg-surface px-3.5 py-3 ${className}`}>
      <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-3">{label}</div>
      <div className={`mt-1.5 text-[19px] font-medium leading-tight tracking-[-0.01em] tnum ${toneCls}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-[11px] leading-snug text-ink-3 tnum">{sub}</div>}
    </div>
  )
}

export function Chip({ tone = 'neutral', children, className = '' }) {
  const cls = {
    neutral: 'border-line bg-surface-2 text-ink-3',
    accent: 'border-accent/40 bg-accent-soft text-accent',
    ok: 'border-ok/35 bg-ok/10 text-ok',
    warn: 'border-warn/35 bg-warn/10 text-warn',
    fail: 'border-fail/35 bg-fail/10 text-fail',
  }[tone]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-[6px] border px-2 py-0.5 text-[10.5px] tnum ${cls} ${className}`}>
      {children}
    </span>
  )
}

export function Table({ head, children, className = '' }) {
  return (
    <div className={`overflow-x-auto rounded-[10px] border border-line ${className}`}>
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr>
            {head.map((h, i) => (
              <th
                key={i}
                className="border-b border-line bg-surface-2 px-2.5 py-2 text-left text-[10px] font-medium uppercase tracking-[0.07em] text-ink-3"
                style={h.width ? { width: h.width } : undefined}
              >
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

export function Td({ mono, dim, className = '', children }) {
  return (
    <td
      className={`border-b border-line/60 px-2.5 py-2 align-top leading-relaxed ${
        mono ? 'font-mono text-[11.5px] text-accent' : dim ? 'text-[11px] text-ink-3' : 'text-ink-2'
      } ${className}`}
    >
      {children}
    </td>
  )
}

/* ── 三种状态：空 / 载入 / 错误，任何异步区域都必须覆盖 ────────── */
export function Empty({ icon: Icon = Inbox, title, desc, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-surface-2">
        <Icon size={17} strokeWidth={1.6} className="text-ink-3" />
      </div>
      <p className="text-[13px] text-ink-2">{title}</p>
      {desc && <p className="mt-1 max-w-[38ch] text-[11.5px] leading-relaxed text-ink-3">{desc}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Loading({ label = '正在推算…' }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14">
      <Loader2 size={18} className="animate-spin text-accent" />
      <p className="mt-3 text-[12px] text-ink-3">{label}</p>
    </div>
  )
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div className="flex items-start gap-2.5 rounded-[10px] border border-fail/30 bg-fail/8 px-3.5 py-3">
      <AlertTriangle size={15} className="mt-0.5 shrink-0 text-fail" />
      <div className="min-w-0 flex-1">
        <p className="text-[12px] leading-relaxed text-[#ffb3a8]">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="mt-1.5 text-[11.5px] text-fail underline underline-offset-2">
            重试
          </button>
        )}
      </div>
    </div>
  )
}
