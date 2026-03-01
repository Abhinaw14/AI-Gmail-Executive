import { useState, useEffect } from 'react'
import { emailsApi } from '../api'
import { Activity, RefreshCw, Zap, Shield, Target, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'

const STATE_COLORS = {
    new: '#6366f1',
    waiting_response: '#f59e0b',
    resolved: '#10b981',
    snoozed: '#8b5cf6',
}

const CLASS_COLORS = {
    urgent: '#ef4444',
    meeting_request: '#6366f1',
    task_request: '#f59e0b',
    decision_required: '#8b5cf6',
    informational: '#06b6d4',
    spam: '#6b7280',
}

export default function AgentLog() {
    const [emails, setEmails] = useState([])
    const [loading, setLoading] = useState(true)

    const load = async () => {
        setLoading(true)
        try {
            const res = await emailsApi.list({ limit: 50, sort_by: 'newest' })
            setEmails(res.data.items || [])
        } catch { }
        setLoading(false)
    }

    useEffect(() => {
        load()
        const interval = setInterval(load, 30000)
        return () => clearInterval(interval)
    }, [])

    const processed = emails.filter(e => e.processed_at)
    const unprocessed = emails.filter(e => !e.processed_at)

    const stats = {
        total: emails.length,
        processed: processed.length,
        pending: unprocessed.length,
        resolved: emails.filter(e => e.state === 'resolved').length,
        urgent: emails.filter(e => e.classification === 'urgent').length,
        spam: emails.filter(e => e.classification === 'spam').length,
        avgPriority: processed.length > 0
            ? Math.round(processed.reduce((s, e) => s + (e.priority_score || 0), 0) / processed.length * 100)
            : 0,
    }

    const statCards = [
        { label: 'Total Emails', value: stats.total, color: '#6366f1', icon: Target },
        { label: 'Processed', value: stats.processed, color: '#10b981', icon: Shield },
        { label: 'Avg Priority', value: `${stats.avgPriority}%`, color: '#f59e0b', icon: TrendingUp },
        { label: 'Urgent', value: stats.urgent, color: '#ef4444', icon: Zap },
    ]

    return (
        <div className="p-6">
            <div className="max-w-4xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold text-white tracking-tight">Agent Activity</h1>
                        <span className="badge" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>
                            <Activity size={11} /> Live
                        </span>
                    </div>
                    <button onClick={load} className="btn-ghost p-2.5 rounded-xl" style={{ color: 'var(--text-muted)' }}>
                        <RefreshCw size={15} />
                    </button>
                </div>

                <p className="text-sm mb-5" style={{ color: 'var(--text-muted)' }}>
                    AI pipeline: <span className="text-white font-medium">Classification → Priority → Sentiment → Context → Deadlines → Memory</span>
                </p>

                {/* Stats */}
                <div className="grid grid-cols-4 gap-3 mb-6">
                    {statCards.map(({ label, value, color, icon: Icon }) => (
                        <motion.div
                            key={label}
                            className="glass-card p-4"
                            style={{ borderColor: `${color}10` }}
                            whileHover={{ y: -2, boxShadow: `0 8px 24px ${color}15` }}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{label}</p>
                                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${color}12` }}>
                                    <Icon size={13} style={{ color }} />
                                </div>
                            </div>
                            <p className="text-2xl font-bold" style={{ color }}>{value}</p>
                        </motion.div>
                    ))}
                </div>

                {loading && (
                    <div className="space-y-2.5">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <div key={i} className="glass-card p-4">
                                <div className="flex items-start gap-3">
                                    <div className="skeleton-line w-9 h-9 rounded-lg" />
                                    <div className="flex-1 space-y-2">
                                        <div className="skeleton-line h-3 rounded w-2/5" />
                                        <div className="skeleton-line h-2.5 rounded w-3/5" />
                                        <div className="flex gap-2">
                                            <div className="skeleton-line h-4 w-16 rounded-full" />
                                            <div className="skeleton-line h-4 w-20 rounded-full" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && emails.length === 0 && (
                    <div className="text-center py-16 glass-card">
                        <Activity size={36} style={{ margin: '0 auto 12px', opacity: 0.15, color: 'var(--text-muted)' }} />
                        <p className="font-medium text-white mb-1">No activity yet</p>
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Emails will appear here once fetched from Gmail</p>
                    </div>
                )}

                {/* Timeline */}
                <div className="relative">
                    {/* Vertical line */}
                    {emails.length > 0 && (
                        <div className="absolute left-[18px] top-4 bottom-4 w-[2px] rounded-full" style={{ background: 'var(--border)' }} />
                    )}

                    <div className="space-y-2.5">
                        {emails.map((e, idx) => {
                            const classColor = CLASS_COLORS[e.classification] || '#6b7280'
                            const stateColor = STATE_COLORS[e.state] || '#6b7280'
                            const isProcessed = !!e.processed_at

                            return (
                                <motion.div
                                    key={e.id}
                                    className="relative pl-10"
                                    initial={{ opacity: 0, x: -8 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx * 0.03 }}
                                >
                                    {/* Timeline dot */}
                                    <div
                                        className="absolute left-[13px] top-4 w-3 h-3 rounded-full border-2 z-10"
                                        style={{
                                            borderColor: isProcessed ? classColor : 'var(--text-muted)',
                                            background: isProcessed ? classColor : 'var(--bg-base)',
                                            boxShadow: isProcessed ? `0 0 8px ${classColor}40` : 'none',
                                        }}
                                    />

                                    <div className="glass-card p-3.5 transition-all duration-200 hover:border-opacity-80"
                                        style={{ opacity: isProcessed ? 1 : 0.6, borderLeft: `3px solid ${classColor}` }}>
                                        <div className="flex items-start justify-between gap-3">
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm text-white font-medium truncate">{e.subject || '(No subject)'}</p>
                                                <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>
                                                    From: {e.sender_name || e.sender} — {e.created_at ? new Date(e.created_at).toLocaleString() : ''}
                                                </p>

                                                <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
                                                    <span className="badge" style={{ background: `${classColor}12`, color: classColor }}>
                                                        {e.classification || 'unclassified'}
                                                    </span>
                                                    {e.priority_score != null && (
                                                        <span className="badge" style={{
                                                            background: e.priority_score >= 0.6 ? 'rgba(239,68,68,0.1)' : e.priority_score >= 0.3 ? 'rgba(245,158,11,0.1)' : 'rgba(34,197,94,0.08)',
                                                            color: e.priority_score >= 0.6 ? '#fca5a5' : e.priority_score >= 0.3 ? '#fbbf24' : '#6ee7b7',
                                                        }}>
                                                            Priority: {Math.round(e.priority_score * 100)}%
                                                        </span>
                                                    )}
                                                    {e.sentiment && (
                                                        <span className="badge" style={{
                                                            background: e.sentiment === 'positive' ? 'rgba(16,185,129,0.1)' : e.sentiment === 'negative' ? 'rgba(239,68,68,0.1)' : 'rgba(100,116,139,0.1)',
                                                            color: e.sentiment === 'positive' ? '#6ee7b7' : e.sentiment === 'negative' ? '#fca5a5' : '#94a3b8',
                                                        }}>
                                                            {e.sentiment}{e.sentiment_tone ? ` · ${e.sentiment_tone}` : ''}
                                                        </span>
                                                    )}
                                                    <span className="badge" style={{ background: `${stateColor}12`, color: stateColor }}>
                                                        {e.state?.replace('_', ' ') || 'new'}
                                                    </span>
                                                    {isProcessed ? (
                                                        <span className="badge" style={{ background: 'rgba(16,185,129,0.08)', color: '#6ee7b7' }}>✓ processed</span>
                                                    ) : (
                                                        <span className="badge" style={{ background: 'rgba(100,116,139,0.08)', color: '#94a3b8' }}>○ pending</span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="text-right flex-shrink-0">
                                                <p className="text-[11px] font-medium" style={{ color: 'var(--text-muted)' }}>
                                                    {e.created_at ? new Date(e.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )
                        })}
                    </div>
                </div>
            </div>
        </div>
    )
}
