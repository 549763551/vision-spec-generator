import { Link, NavLink } from 'react-router-dom'
import { ArrowUpRight } from 'lucide-react'

const links = [
  { to: '/studio', label: '方案工作台' },
  { to: '/about', label: '边界与方法' },
]

export default function AppShell({ children }) {
  return (
    <div className="min-h-screen overflow-x-clip top-sheen">
      <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-6 gap-y-1 px-5 py-2.5 sm:h-14 sm:flex-nowrap sm:px-7 sm:py-0">
          <Link to="/" className="group flex items-center gap-2.5">
            <span className="h-2 w-2 rounded-full bg-accent shadow-[0_0_10px_#2fd3c5]" />
            <span className="text-[13.5px] font-medium tracking-[-0.01em] text-ink-1">
              Vision Spec
            </span>
          </Link>

          <nav className="-ml-1 flex items-center gap-0.5 sm:gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded-[7px] px-2.5 py-1.5 text-[12.5px] transition-colors ${
                    isActive ? 'bg-surface-2 text-ink-1' : 'text-ink-3 hover:text-ink-1'
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
            <a
              href="/exploded"
              className="group flex items-center gap-1 rounded-[7px] px-2.5 py-1.5 text-[12.5px] text-ink-3 transition-colors hover:text-ink-1"
            >
              3D 拆解
              <ArrowUpRight size={12} className="opacity-50 transition-opacity group-hover:opacity-100" />
            </a>
          </nav>

          <div className="ml-auto hidden items-center gap-3 sm:flex">
            <span className="hidden text-[10.5px] tracking-[0.04em] text-ink-3/80 tnum sm:block">
              v0.2.0
            </span>
          </div>
        </div>
      </header>

      <main>{children}</main>

      <footer className="mt-20 border-t border-line">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-2 px-5 py-6 text-[11px] text-ink-3 sm:flex-row sm:items-center sm:justify-between sm:px-7">
          <span>Vision Spec Generator · 成像方案自动生成器</span>
          <span className="tnum">四组计算 · 自检复算 · 四平台导出</span>
        </div>
      </footer>
    </div>
  )
}
