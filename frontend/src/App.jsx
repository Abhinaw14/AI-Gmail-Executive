import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Mail, Calendar, BarChart2, Bot, Sparkles } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import Inbox from './pages/Inbox'
import CalendarPage from './pages/CalendarPage'
import Reports from './pages/Reports'
import AgentLog from './pages/AgentLog'
import './App.css'

const NAV = [
  { to: '/', icon: Mail, label: 'Inbox' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/reports', icon: BarChart2, label: 'Reports' },
  { to: '/agent-log', icon: Bot, label: 'Agent Log' },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-base)' }}>
        {/* ── Sidebar ── */}
        <aside
          className="w-[260px] flex-shrink-0 flex flex-col relative"
          style={{
            background: 'rgba(12, 12, 22, 0.85)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            borderRight: '1px solid var(--border)',
          }}
        >
          {/* Top glow accent */}
          <div
            className="absolute top-0 left-0 right-0 h-[1px]"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(99,102,241,0.4), rgba(6,182,212,0.3), transparent)' }}
          />

          {/* Logo */}
          <div className="px-5 py-5 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center relative overflow-hidden"
                style={{ background: 'var(--gradient-accent)', boxShadow: '0 4px 16px rgba(99,102,241,0.3)' }}
              >
                <Sparkles size={20} className="text-white relative z-10" />
                <div
                  className="absolute inset-0 opacity-50"
                  style={{
                    background: 'linear-gradient(135deg, transparent 40%, rgba(255,255,255,0.2) 50%, transparent 60%)',
                    animation: 'shimmer 3s ease-in-out infinite',
                  }}
                />
              </div>
              <div>
                <p className="font-bold text-sm text-white leading-tight tracking-tight">AI Assistant</p>
                <p className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>Executive Mode</p>
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 px-3 py-4 space-y-1">
            {NAV.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `group flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 relative ${isActive
                    ? 'text-white'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]'
                  }`
                }
                style={({ isActive }) => isActive ? {
                  background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(6,182,212,0.08))',
                  boxShadow: 'inset 0 0 0 1px rgba(99,102,241,0.15)',
                } : {}}
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <div
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                        style={{ background: 'var(--gradient-primary)' }}
                      />
                    )}
                    <Icon size={17} style={isActive ? { color: 'var(--primary-light)' } : {}} />
                    <span>{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Status */}
          <div className="px-5 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-2.5 text-[11px]" style={{ color: 'var(--text-muted)' }}>
              <span
                className="w-2 h-2 rounded-full bg-emerald-400"
                style={{ boxShadow: '0 0 8px rgba(52,211,153,0.5)', animation: 'pulseGlow 2s ease-in-out infinite' }}
              />
              <span>System active · Polling 60s</span>
            </div>
          </div>
        </aside>

        {/* ── Main ── */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Inbox />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/agent-log" element={<AgentLog />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
