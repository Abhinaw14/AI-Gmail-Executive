import { useState, useEffect } from 'react'
import { calendarApi } from '../api'
import { Users, Video, Plus, AlertTriangle, Target, ChevronLeft, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const URGENCY = {
    critical: { emoji: '🔴', color: '#ef4444', bg: 'rgba(239,68,68,0.08)', label: 'Critical' },
    high: { emoji: '🟠', color: '#f97316', bg: 'rgba(249,115,22,0.08)', label: 'High' },
    medium: { emoji: '🟡', color: '#eab308', bg: 'rgba(234,179,8,0.08)', label: 'Medium' },
    low: { emoji: '🟢', color: '#22c55e', bg: 'rgba(34,197,94,0.08)', label: 'Low' },
}

const TYPE_ICONS = {
    submission: '📄', meeting: '🤝', exam: '📝', interview: '💼',
    payment: '💳', event: '🎯', reminder: '⏰', other: '📌',
}

export default function CalendarPage() {
    const [events, setEvents] = useState([])
    const [deadlines, setDeadlines] = useState([])
    const [loading, setLoading] = useState(true)
    const [loadingDeadlines, setLoadingDeadlines] = useState(false)
    const [showCreate, setShowCreate] = useState(false)
    const [form, setForm] = useState({ title: '', start_iso: '', end_iso: '', attendees: '', description: '' })
    const [creating, setCreating] = useState(false)
    const [addingId, setAddingId] = useState(null)

    const loadCalendar = async () => {
        setLoading(true)
        try {
            const eventsRes = await calendarApi.events(14)
            setEvents(eventsRes.data.events || [])
        } catch { }
        setLoading(false)
    }

    const scanDeadlines = async () => {
        setLoadingDeadlines(true)
        try {
            const { data } = await calendarApi.deadlines(14)
            setDeadlines(data.deadlines || [])
        } catch { }
        setLoadingDeadlines(false)
    }

    useEffect(() => { loadCalendar(); scanDeadlines() }, [])

    const handleCreate = async (e) => {
        e.preventDefault()
        setCreating(true)
        try {
            await calendarApi.createEvent({
                ...form,
                attendees: form.attendees.split(',').map(s => s.trim()).filter(Boolean),
            })
            setShowCreate(false)
            setForm({ title: '', start_iso: '', end_iso: '', attendees: '', description: '' })
            await loadCalendar()
        } catch { alert('Failed to create event') }
        setCreating(false)
    }

    const handleAddDeadline = async (dl, idx) => {
        setAddingId(idx)
        try {
            await calendarApi.addFromEmail({
                email_id: dl.email_id,
                title: dl.title,
                date: dl.date,
                time: dl.time,
                urgency: dl.urgency,
                type: dl.type,
                description: dl.description,
                email_subject: dl.email_subject,
                email_sender: dl.email_sender,
            })
            await loadCalendar()
            setDeadlines(prev => prev.map((d, i) => i === idx ? { ...d, _added: true } : d))
        } catch { alert('Failed to add to calendar') }
        setAddingId(null)
    }

    const [currentDate, setCurrentDate] = useState(new Date())

    const changeMonth = (offset) => {
        setCurrentDate(prev => {
            const next = new Date(prev)
            next.setMonth(next.getMonth() + offset)
            return next
        })
    }

    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()
    const firstDayOfMonth = new Date(year, month, 1).getDay()
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const daysInPrevMonth = new Date(year, month, 0).getDate()

    const gridDays = []
    for (let i = 0; i < firstDayOfMonth; i++) {
        gridDays.push({ day: daysInPrevMonth - firstDayOfMonth + i + 1, isCurrentMonth: false, dateObj: new Date(year, month - 1, daysInPrevMonth - firstDayOfMonth + i + 1) })
    }
    for (let i = 1; i <= daysInMonth; i++) {
        gridDays.push({ day: i, isCurrentMonth: true, dateObj: new Date(year, month, i), isToday: new Date().toDateString() === new Date(year, month, i).toDateString() })
    }
    const remainingSlots = 42 - gridDays.length
    for (let i = 1; i <= remainingSlots; i++) {
        gridDays.push({ day: i, isCurrentMonth: false, dateObj: new Date(year, month + 1, i) })
    }

    const eventsByDate = {}
    events.forEach(ev => {
        if (!ev.start) return
        const dStr = new Date(ev.start).toDateString()
        if (!eventsByDate[dStr]) eventsByDate[dStr] = []
        eventsByDate[dStr].push(ev)
    })

    const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    const monthName = currentDate.toLocaleString('default', { month: 'long', year: 'numeric' })

    return (
        <div className="p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-white tracking-tight">Calendar</h1>
                        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                            Upcoming events and deadlines
                        </p>
                    </div>
                    <div className="flex gap-2.5">
                        <button
                            onClick={scanDeadlines}
                            disabled={loadingDeadlines}
                            className="btn-ghost flex items-center gap-2 px-4 py-2.5 text-sm font-medium"
                            style={{ color: '#a5b4fc', borderColor: 'rgba(99,102,241,0.2)' }}
                        >
                            <Target size={15} />
                            {loadingDeadlines ? (
                                <span className="flex items-center gap-2">
                                    <span className="w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                                    Scanning...
                                </span>
                            ) : 'Scan Deadlines'}
                        </button>
                        <button
                            onClick={() => setShowCreate(!showCreate)}
                            className="btn-primary flex items-center gap-2 px-4 py-2.5 text-sm"
                        >
                            <Plus size={15} /> New Event
                        </button>
                    </div>
                </div>

                {/* Create Event Form */}
                <AnimatePresence>
                    {showCreate && (
                        <motion.form
                            onSubmit={handleCreate}
                            className="glass-card-elevated p-6 mb-6"
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -8 }}
                        >
                            <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
                                <Plus size={16} style={{ color: 'var(--primary-light)' }} />
                                Create Calendar Event
                            </h2>
                            <div className="grid grid-cols-2 gap-3">
                                {[
                                    { key: 'title', label: 'Title', type: 'text', full: true },
                                    { key: 'start_iso', label: 'Start', type: 'datetime-local' },
                                    { key: 'end_iso', label: 'End', type: 'datetime-local' },
                                    { key: 'attendees', label: 'Attendees (comma-separated emails)', type: 'text', full: true },
                                    { key: 'description', label: 'Description', type: 'text', full: true },
                                ].map(({ key, label, type, full }) => (
                                    <div key={key} className={full ? 'col-span-2' : ''}>
                                        <label className="text-[11px] font-medium uppercase tracking-wider mb-1.5 block" style={{ color: 'var(--text-muted)' }}>{label}</label>
                                        <input
                                            type={type}
                                            value={form[key]}
                                            onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                                            className="w-full text-sm px-3.5 py-2.5 rounded-xl border outline-none transition-all"
                                            style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
                                        />
                                    </div>
                                ))}
                            </div>
                            <div className="flex gap-3 mt-5">
                                <button type="submit" disabled={creating} className="btn-primary px-5 py-2.5 text-sm flex items-center gap-2">
                                    {creating ? (
                                        <><span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Creating...</>
                                    ) : 'Create Event'}
                                </button>
                                <button type="button" onClick={() => setShowCreate(false)} className="btn-ghost px-4 py-2.5 text-sm">Cancel</button>
                            </div>
                        </motion.form>
                    )}
                </AnimatePresence>

                {/* Pending Deadlines */}
                <AnimatePresence>
                    {deadlines.length > 0 && (
                        <motion.div
                            className="glass-card p-4 mb-6 sticky top-0 z-10"
                            style={{ borderColor: 'rgba(245,158,11,0.2)' }}
                            initial={{ opacity: 0, y: -8 }}
                            animate={{ opacity: 1, y: 0 }}
                        >
                            <div className="flex items-center justify-between mb-3">
                                <h2 className="font-semibold text-white flex items-center gap-2 text-sm">
                                    <AlertTriangle size={15} style={{ color: '#f59e0b' }} />
                                    {deadlines.length} Detected Deadlines
                                </h2>
                            </div>
                            <div className="flex gap-3 overflow-x-auto pb-2">
                                {deadlines.map((dl, i) => {
                                    const u = URGENCY[dl.urgency] || URGENCY.medium
                                    return (
                                        <div key={i} className="flex-shrink-0 p-3.5 rounded-xl border w-72 flex flex-col justify-between transition-all hover:border-opacity-60"
                                            style={{ background: 'var(--bg-base)', borderColor: `${u.color}22` }}>
                                            <div>
                                                <div className="flex items-center gap-2 mb-1.5">
                                                    <span className="badge" style={{ background: `${u.color}15`, color: u.color }}>
                                                        {u.emoji} {dl.type}
                                                    </span>
                                                    <p className="text-xs font-medium text-white truncate flex-1">{dl.title}</p>
                                                </div>
                                                <p className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                                                    📅 {dl.date} {dl.time || ''}
                                                </p>
                                            </div>
                                            <div className="mt-3">
                                                {dl._added ? (
                                                    <span className="badge w-full justify-center" style={{ background: 'rgba(16,185,129,0.1)', color: '#6ee7b7' }}>✓ Added</span>
                                                ) : (
                                                    <button
                                                        onClick={() => handleAddDeadline(dl, i)}
                                                        disabled={addingId === i}
                                                        className="btn-ghost text-[10px] px-2.5 py-1.5 w-full font-medium"
                                                        style={{ color: '#fbbf24', borderColor: 'rgba(245,158,11,0.25)' }}
                                                    >
                                                        {addingId === i ? (
                                                            <span className="w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full animate-spin block mx-auto" />
                                                        ) : '+ Add to Calendar'}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Monthly Grid */}
                <div className="glass-card-elevated flex flex-col overflow-hidden" style={{ minHeight: 700 }}>
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'var(--border)' }}>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2.5">
                            <span style={{ color: 'var(--primary-light)' }}>📅</span> {monthName}
                        </h2>
                        <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)' }}>
                            <button onClick={() => changeMonth(-1)} className="p-2 rounded-lg hover:bg-white/10 text-white transition-all">
                                <ChevronLeft size={16} />
                            </button>
                            <button onClick={() => setCurrentDate(new Date())} className="px-3.5 py-1.5 text-sm font-medium hover:bg-white/10 rounded-lg text-white transition-all">
                                Today
                            </button>
                            <button onClick={() => changeMonth(1)} className="p-2 rounded-lg hover:bg-white/10 text-white transition-all">
                                <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>

                    {/* Weekday Labels */}
                    <div className="grid grid-cols-7 border-b" style={{ borderColor: 'var(--border)', background: 'rgba(255,255,255,0.015)' }}>
                        {WEEKDAYS.map(day => (
                            <div key={day} className="py-2.5 text-center text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                                {day}
                            </div>
                        ))}
                    </div>

                    {/* Grid */}
                    <div className="grid grid-cols-7 flex-1 auto-rows-fr">
                        {gridDays.map((dateObj, i) => {
                            const dStr = dateObj.dateObj.toDateString()
                            const dayEvents = eventsByDate[dStr] || []
                            dayEvents.sort((a, b) => (b.description?.includes('AI') ? 1 : 0) - (a.description?.includes('AI') ? 1 : 0))

                            return (
                                <div key={i} className="min-h-[110px] border-b border-r p-1.5 transition-colors hover:bg-white/[0.015]"
                                    style={{
                                        borderColor: 'var(--border)',
                                        background: dateObj.isCurrentMonth ? 'transparent' : 'rgba(0,0,0,0.15)',
                                        opacity: dateObj.isCurrentMonth ? 1 : 0.35
                                    }}>
                                    <div className="flex items-center justify-between mb-1.5 px-1">
                                        <span className={`text-sm font-semibold w-7 h-7 flex items-center justify-center rounded-full transition-all ${dateObj.isToday
                                            ? 'text-white'
                                            : 'text-slate-400'
                                            }`}
                                            style={dateObj.isToday ? {
                                                background: 'var(--gradient-primary)',
                                                boxShadow: '0 2px 12px rgba(99,102,241,0.4)',
                                            } : {}}
                                        >
                                            {dateObj.day}
                                        </span>
                                    </div>
                                    <div className="space-y-1 overflow-y-auto max-h-[80px] pr-1">
                                        {dayEvents.map(ev => {
                                            const isAI = ev.description?.includes('AI')
                                            const time = ev.start ? new Date(ev.start).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : 'All Day'
                                            const hasMeet = ev.meet_link || (ev.description && ev.description.includes('meet.google.com'))
                                            return (
                                                <div key={ev.id} className="text-[10px] p-1.5 rounded-lg truncate flex items-center gap-1.5 cursor-pointer transition-all hover:opacity-80"
                                                    style={{
                                                        background: isAI ? 'rgba(245,158,11,0.1)' : 'rgba(99,102,241,0.1)',
                                                        color: isAI ? '#fbbf24' : '#a5b4fc',
                                                        borderLeft: `2px solid ${isAI ? '#f59e0b' : '#6366f1'}`
                                                    }}
                                                    title={`${time} - ${ev.title}`}>
                                                    <span className="opacity-60">{time}</span>
                                                    <span className="font-medium truncate flex-1">{ev.title}</span>
                                                    {hasMeet && <Video size={10} className="flex-shrink-0" />}
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>
        </div>
    )
}
