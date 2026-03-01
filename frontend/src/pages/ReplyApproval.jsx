import { useState, useEffect } from 'react'
import { repliesApi } from '../api'
import { CheckCircle, XCircle, Edit3, ChevronDown, ChevronUp, Sparkles, Send } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

function ConfidenceBadge({ score }) {
    const pct = Math.round((score || 0) * 100)
    const color = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444'
    return (
        <span className="badge" style={{ background: `${color}12`, color }}>
            {pct}% confidence
        </span>
    )
}

function DraftCard({ draft, onApprove, onReject, onEdit }) {
    const [showAlt, setShowAlt] = useState(false)
    const [editing, setEditing] = useState(false)
    const [editContent, setEditContent] = useState(draft.edited_content || draft.main_reply)
    const [loading, setLoading] = useState(false)

    const handleSaveEdit = async () => {
        await onEdit(draft.id, editContent)
        setEditing(false)
    }

    const handleApprove = async () => {
        setLoading(true)
        await onApprove(draft.id)
        setLoading(false)
    }

    return (
        <motion.div
            className="glass-card-elevated p-6 mb-4"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
        >
            {/* Header */}
            <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--gradient-accent)' }}>
                        <Sparkles size={15} className="text-white" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-white">{draft.email_subject || '(No subject)'}</h3>
                        <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>To: {draft.email_sender}</p>
                    </div>
                </div>
                <ConfidenceBadge score={draft.confidence_score} />
            </div>

            {/* Explanation */}
            {draft.explanation && (
                <div className="p-3.5 rounded-xl mb-4 text-sm flex items-start gap-2" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.1)' }}>
                    <Sparkles size={13} className="flex-shrink-0 mt-0.5" style={{ color: '#818cf8' }} />
                    <span style={{ color: 'var(--text-secondary)' }}>{draft.explanation}</span>
                </div>
            )}

            {/* Summary */}
            {draft.summary && (
                <div className="mb-4">
                    <p className="text-[11px] font-medium uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>Summary</p>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{draft.summary}</p>
                </div>
            )}

            {/* Action items */}
            {draft.action_items?.length > 0 && (
                <div className="mb-4 p-3.5 rounded-xl" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.1)' }}>
                    <p className="text-[11px] font-medium uppercase tracking-wider mb-2" style={{ color: '#fbbf24' }}>Action Items</p>
                    <ul className="space-y-1.5">
                        {draft.action_items.map((item, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
                                <span style={{ color: '#818cf8', marginTop: 1 }}>•</span> {item}
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* Calendar slots */}
            {draft.calendar_slots?.length > 0 && (
                <div className="mb-4 p-3.5 rounded-xl" style={{ background: 'rgba(6,182,212,0.06)', borderLeft: '3px solid #06b6d4' }}>
                    <p className="text-[11px] font-medium uppercase tracking-wider mb-2" style={{ color: '#06b6d4' }}>Suggested Slots</p>
                    {draft.calendar_slots.slice(0, 3).map((s, i) => (
                        <p key={i} className="text-sm" style={{ color: 'var(--text-secondary)' }}>🕐 {s.display || s.start}</p>
                    ))}
                </div>
            )}

            {/* Main reply */}
            <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                    <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>Reply Draft</p>
                    <button
                        onClick={() => setEditing(!editing)}
                        className="btn-ghost flex items-center gap-1.5 text-xs px-2.5 py-1.5"
                    >
                        <Edit3 size={12} /> Edit
                    </button>
                </div>
                <AnimatePresence mode="wait">
                    {editing ? (
                        <motion.div
                            key="edit"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                        >
                            <textarea
                                value={editContent}
                                onChange={e => setEditContent(e.target.value)}
                                rows={6}
                                className="w-full text-sm p-4 rounded-xl border outline-none resize-none transition-all"
                                style={{
                                    background: 'rgba(255,255,255,0.02)',
                                    borderColor: 'var(--border)',
                                    color: 'var(--text-primary)',
                                    lineHeight: 1.7,
                                }}
                            />
                            <div className="flex gap-2 mt-2.5">
                                <button onClick={handleSaveEdit} className="btn-primary text-xs px-4 py-2">Save</button>
                                <button onClick={() => setEditing(false)} className="btn-ghost text-xs px-3 py-2">Cancel</button>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.div
                            key="view"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-sm p-4 rounded-xl whitespace-pre-wrap leading-relaxed"
                            style={{ background: 'rgba(255,255,255,0.02)', color: 'var(--text-secondary)', border: '1px solid var(--border)' }}
                        >
                            {draft.edited_content || draft.main_reply}
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Alt reply toggle */}
            {draft.alternative_reply && (
                <div className="mb-4">
                    <button
                        onClick={() => setShowAlt(!showAlt)}
                        className="btn-ghost flex items-center gap-1.5 text-xs px-2.5 py-1.5 mb-2"
                    >
                        {showAlt ? <ChevronUp size={12} /> : <ChevronDown size={12} />} Alternative Reply
                    </button>
                    <AnimatePresence>
                        {showAlt && (
                            <motion.div
                                className="text-sm p-4 rounded-xl whitespace-pre-wrap leading-relaxed"
                                style={{ background: 'rgba(255,255,255,0.02)', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                {draft.alternative_reply}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            )}

            {/* Buttons */}
            <div className="flex gap-3 mt-5 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
                <button
                    onClick={handleApprove}
                    disabled={loading}
                    className="btn-success flex-1 flex items-center justify-center gap-2 py-2.5 text-sm"
                >
                    {loading ? (
                        <>
                            <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            Sending...
                        </>
                    ) : (
                        <>
                            <Send size={14} />
                            Approve & Send
                        </>
                    )}
                </button>
                <button
                    onClick={() => onReject(draft.id)}
                    className="btn-danger-outline flex items-center gap-2 px-5 py-2.5 text-sm font-medium"
                >
                    <XCircle size={14} /> Reject
                </button>
            </div>
        </motion.div>
    )
}

export default function ReplyApproval() {
    const [drafts, setDrafts] = useState([])
    const [loading, setLoading] = useState(true)

    const load = async () => {
        setLoading(true)
        try {
            const { data } = await repliesApi.pending()
            setDrafts(data || [])
        } catch { setDrafts([]) }
        setLoading(false)
    }

    useEffect(() => { load() }, [])

    const handleApprove = async (id) => {
        try { await repliesApi.approve(id); await load() }
        catch (e) { alert('Failed to send reply') }
    }

    const handleReject = async (id) => {
        await repliesApi.reject(id)
        await load()
    }

    const handleEdit = async (id, content) => {
        await repliesApi.edit(id, content)
        await load()
    }

    return (
        <div className="p-6">
            <div className="max-w-3xl mx-auto">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white tracking-tight">Reply Approval</h1>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        {drafts.length} draft{drafts.length !== 1 ? 's' : ''} awaiting your approval
                    </p>
                </div>

                {loading && (
                    <div className="space-y-4">
                        {Array.from({ length: 2 }).map((_, i) => (
                            <div key={i} className="glass-card p-6">
                                <div className="flex items-start gap-3 mb-4">
                                    <div className="skeleton-line w-9 h-9 rounded-lg" />
                                    <div className="flex-1 space-y-2">
                                        <div className="skeleton-line h-4 rounded w-2/5" />
                                        <div className="skeleton-line h-3 rounded w-1/3" />
                                    </div>
                                    <div className="skeleton-line h-6 w-24 rounded-full" />
                                </div>
                                <div className="space-y-2">
                                    <div className="skeleton-line h-3 rounded w-full" />
                                    <div className="skeleton-line h-3 rounded w-11/12" />
                                    <div className="skeleton-line h-3 rounded w-4/5" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {!loading && drafts.length === 0 && (
                    <div className="text-center py-16 glass-card">
                        <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-3" style={{ background: 'rgba(16,185,129,0.08)' }}>
                            <CheckCircle size={28} style={{ color: '#6ee7b7', opacity: 0.6 }} />
                        </div>
                        <p className="font-semibold text-white mb-1">All caught up!</p>
                        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No pending reply drafts</p>
                    </div>
                )}

                {drafts.map(draft => (
                    <DraftCard
                        key={draft.id}
                        draft={draft}
                        onApprove={handleApprove}
                        onReject={handleReject}
                        onEdit={handleEdit}
                    />
                ))}
            </div>
        </div>
    )
}
