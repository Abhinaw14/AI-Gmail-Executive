import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { emailsApi, searchApi, calendarApi } from '../api'
import { Mail, AlertCircle, Calendar, CheckSquare, Info, Zap, Search, X, SortAsc, Send, Sparkles, RotateCcw, CalendarPlus, XCircle, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const CLASSIFICATIONS = {
    urgent: { label: 'Urgent', color: '#ef4444', icon: AlertCircle },
    meeting_request: { label: 'Meeting', color: '#6366f1', icon: Calendar },
    task_request: { label: 'Task', color: '#f59e0b', icon: CheckSquare },
    decision_required: { label: 'Decision', color: '#8b5cf6', icon: Zap },
    informational: { label: 'Info', color: '#06b6d4', icon: Info },
    spam: { label: 'Spam', color: '#6b7280', icon: Mail },
}

const STATES = {
    open: { bg: 'rgba(59,130,246,0.12)', color: '#93c5fd', label: 'Open' },
    waiting_response: { bg: 'rgba(234,179,8,0.12)', color: '#fde047', label: 'Waiting' },
    resolved: { bg: 'rgba(16,185,129,0.12)', color: '#6ee7b7', label: 'Resolved' },
    follow_up_pending: { bg: 'rgba(249,115,22,0.12)', color: '#fdba74', label: 'Follow-up' },
}

const SORT_OPTIONS = [
    { value: 'newest', label: 'Newest First' },
    { value: 'priority_newest', label: 'Smart (Priority + Recency)' },
    { value: 'priority', label: 'Priority First' },
]

// ── Avatar from initials ──
function SenderAvatar({ name, size = 36 }) {
    const initials = useMemo(() => {
        if (!name) return '?'
        const parts = name.split(/[\s@.]+/).filter(Boolean)
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
        return name.slice(0, 2).toUpperCase()
    }, [name])

    const gradient = useMemo(() => {
        let hash = 0
        for (let i = 0; i < (name || '').length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash)
        const hue = Math.abs(hash) % 360
        return `linear-gradient(135deg, hsl(${hue}, 65%, 45%), hsl(${(hue + 40) % 360}, 55%, 55%))`
    }, [name])

    return (
        <div
            className="flex-shrink-0 rounded-xl flex items-center justify-center font-bold text-white"
            style={{ width: size, height: size, background: gradient, fontSize: size * 0.36, letterSpacing: '-0.02em' }}
        >
            {initials}
        </div>
    )
}

// ── Relative Time ──
function relativeTime(dateStr) {
    if (!dateStr) return ''
    const diff = Date.now() - new Date(dateStr).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'Just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.floor(hrs / 24)
    if (days < 7) return `${days}d ago`
    return new Date(dateStr).toLocaleDateString()
}

// ── Priority Bar ──
function PriorityBar({ score }) {
    const pct = Math.round((score || 0) * 100)
    const color = pct >= 80 ? '#ef4444' : pct >= 60 ? '#f59e0b' : pct >= 40 ? '#6366f1' : '#10b981'
    return (
        <div className="flex items-center gap-2.5">
            <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                <motion.div
                    className="h-full rounded-full"
                    style={{ background: color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut' }}
                />
            </div>
            <span className="text-[11px] font-semibold tabular-nums" style={{ color, minWidth: 32 }}>{pct}%</span>
        </div>
    )
}

// ── Skeleton Loader ──
function EmailSkeleton() {
    return (
        <div className="space-y-0">
            {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-start gap-3">
                        <div className="skeleton-line w-9 h-9 rounded-xl flex-shrink-0" />
                        <div className="flex-1 space-y-2">
                            <div className="skeleton-line h-3 rounded w-2/5" />
                            <div className="skeleton-line h-2.5 rounded w-3/4" />
                            <div className="skeleton-line h-2 rounded w-1/4" />
                        </div>
                        <div className="skeleton-line h-5 w-14 rounded-full" />
                    </div>
                    <div className="skeleton-line h-1.5 rounded-full mt-3" />
                </div>
            ))}
        </div>
    )
}

// ── Typing Indicator ──
function TypingIndicator() {
    return (
        <div className="flex items-center gap-3 p-4">
            <div
                className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: 'var(--gradient-accent)', boxShadow: '0 2px 12px rgba(99,102,241,0.2)' }}
            >
                <Sparkles size={14} className="text-white" />
            </div>
            <div className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl" style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)' }}>
                <div className="typing-dot" />
                <div className="typing-dot" />
                <div className="typing-dot" />
            </div>
            <span className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>AI is composing a reply...</span>
        </div>
    )
}

// ── Search Bar Component ──
function SearchBar({ onResults, onClear }) {
    const [query, setQuery] = useState('')
    const [sender, setSender] = useState('')
    const [subject, setSubject] = useState('')
    const [expanded, setExpanded] = useState(false)
    const [searching, setSearching] = useState(false)
    const debounceRef = useRef(null)

    const runSearch = useCallback(async (q, s, sub) => {
        if (!q && !s && !sub) { onClear(); return }
        setSearching(true)
        try {
            const { data } = await searchApi.search({
                q: q || undefined,
                sender: s || undefined,
                subject: sub || undefined,
                limit: 50,
            })
            onResults(data.items || [], data.total || 0, q)
        } catch { onClear() }
        setSearching(false)
    }, [onResults, onClear])

    const handleChange = (field, value) => {
        if (field === 'q') setQuery(value)
        if (field === 'sender') setSender(value)
        if (field === 'subject') setSubject(value)

        clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => {
            const q2 = field === 'q' ? value : query
            const s2 = field === 'sender' ? value : sender
            const sub2 = field === 'subject' ? value : subject
            runSearch(q2, s2, sub2)
        }, 400)
    }

    const handleClear = () => {
        setQuery(''); setSender(''); setSubject('')
        onClear()
    }

    const hasInput = query || sender || subject

    return (
        <div className="px-3 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <div
                className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl transition-all duration-200"
                style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: `1px solid ${hasInput ? 'rgba(99,102,241,0.3)' : 'var(--border)'}`,
                    boxShadow: hasInput ? '0 0 0 3px rgba(99,102,241,0.06)' : 'none',
                }}
            >
                {searching
                    ? <div className="w-4 h-4 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                    : <Search size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                }
                <input
                    value={query}
                    onChange={e => handleChange('q', e.target.value)}
                    placeholder="Search emails..."
                    className="flex-1 bg-transparent outline-none text-sm text-white placeholder-slate-500"
                />
                {hasInput && (
                    <button onClick={handleClear} className="p-1 rounded-lg hover:bg-white/10 transition-colors">
                        <X size={13} style={{ color: 'var(--text-muted)' }} />
                    </button>
                )}
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="text-[11px] font-medium px-2 py-1 rounded-lg transition-all hover:bg-white/10"
                    style={{ color: expanded ? '#818cf8' : 'var(--text-muted)' }}
                >
                    Filters
                </button>
            </div>

            <AnimatePresence>
                {expanded && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        <div className="mt-2.5 grid grid-cols-2 gap-2">
                            {[
                                { key: 'sender', placeholder: 'Filter by sender...', value: sender },
                                { key: 'subject', placeholder: 'Filter by subject...', value: subject },
                            ].map(({ key, placeholder, value }) => (
                                <input
                                    key={key}
                                    value={value}
                                    onChange={e => handleChange(key, e.target.value)}
                                    placeholder={placeholder}
                                    className="text-xs px-3 py-2 rounded-xl border outline-none transition-all"
                                    style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)', color: '#e2e8f0' }}
                                />
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {hasInput && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                    {query && <span className="badge" style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>"{query}"</span>}
                    {sender && <span className="badge" style={{ background: 'rgba(6,182,212,0.12)', color: '#67e8f9' }}>from: {sender}</span>}
                    {subject && <span className="badge" style={{ background: 'rgba(245,158,11,0.12)', color: '#fcd34d' }}>subject: {subject}</span>}
                </div>
            )}
        </div>
    )
}

// ── Email List Item ──
function EmailItem({ email, selected, onClick, semanticScore }) {
    const isProcessing = email.processing_status === 'processing'
    const C = CLASSIFICATIONS[email.classification] || CLASSIFICATIONS.informational
    const Icon = C.icon
    const isSelected = selected?.id === email.id
    const S = STATES[email.state] || { bg: 'rgba(100,116,139,0.12)', color: '#94a3b8', label: email.state?.replace('_', ' ') || 'Unknown' }

    return (
        <motion.button
            onClick={() => onClick(email)}
            className="w-full text-left p-3.5 border-b transition-all duration-200 group relative"
            style={{
                borderColor: 'var(--border)',
                background: isSelected ? 'rgba(99,102,241,0.08)' : 'transparent',
                borderLeft: `3px solid ${isSelected ? C.color : 'transparent'}`,
            }}
            whileHover={{ backgroundColor: isSelected ? 'rgba(99,102,241,0.08)' : 'rgba(255,255,255,0.03)' }}
        >
            {/* Selected glow */}
            {isSelected && (
                <div className="absolute inset-0 pointer-events-none" style={{
                    background: `linear-gradient(90deg, ${C.color}08, transparent)`,
                }} />
            )}

            <div className="flex items-start gap-3 relative">
                <SenderAvatar name={email.sender_name || email.sender} size={36} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                        <p className="text-[13px] font-semibold text-white truncate">
                            {email.sender_name || email.sender}
                        </p>
                        {isProcessing && (
                            <span className="badge animate-pulse" style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc', fontSize: 10 }}>
                                ⚡ Processing
                            </span>
                        )}
                        {!isProcessing && semanticScore && (
                            <span className="badge" style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc', fontSize: 10 }}>
                                {Math.round(semanticScore * 100)}%
                            </span>
                        )}
                    </div>
                    <p className="text-xs truncate mb-1" style={{ color: 'var(--text-secondary)' }}>{email.subject}</p>
                    <div className="flex items-center gap-2">
                        <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                            {relativeTime(email.created_at)}
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--text-faint)' }}>·</span>
                        <div className="flex items-center gap-1">
                            <Icon size={10} style={{ color: C.color }} />
                            <span className="text-[10px] font-medium" style={{ color: C.color }}>{C.label}</span>
                        </div>
                    </div>
                </div>
                <div className="flex flex-col items-end gap-1.5">
                    <span className="badge" style={{ background: S.bg, color: S.color, fontSize: 10 }}>
                        {S.label}
                    </span>
                    <ChevronRight
                        size={12}
                        className="opacity-0 group-hover:opacity-50 transition-opacity"
                        style={{ color: 'var(--text-muted)' }}
                    />
                </div>
            </div>

            {/* Priority bar */}
            <div className="mt-2.5 relative">
                {isProcessing ? (
                    <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(99,102,241,0.08)' }}>
                        <div className="h-full rounded-full animate-pulse" style={{ width: '30%', background: 'rgba(99,102,241,0.3)' }} />
                    </div>
                ) : (
                    <PriorityBar score={email.priority_score} />
                )}
            </div>
        </motion.button>
    )
}

// ── Main Inbox Page ──
export default function Inbox() {
    const [emails, setEmails] = useState([])
    const [total, setTotal] = useState(0)
    const [loading, setLoading] = useState(true)
    const [loadingMore, setLoadingMore] = useState(false)
    const [filter, setFilter] = useState({ state: '', classification: '', sort_by: 'newest' })
    const [offset, setOffset] = useState(0)
    const [selected, setSelected] = useState(null)
    const [loadingDetail, setLoadingDetail] = useState(false)
    const [processing, setProcessing] = useState(null)
    const [processError, setProcessError] = useState(null)
    const [replyDraft, setReplyDraft] = useState(null)
    const [editedReply, setEditedReply] = useState('')
    const [useAlt, setUseAlt] = useState(false)
    const [sending, setSending] = useState(false)
    const [sentSuccess, setSentSuccess] = useState(false)
    const [emailDeadlines, setEmailDeadlines] = useState([])
    const [detectingDeadlines, setDetectingDeadlines] = useState(false)
    const [addingDeadlineIdx, setAddingDeadlineIdx] = useState(null)
    const [searchMode, setSearchMode] = useState(false)
    const [searchResults, setSearchResults] = useState([])
    const [searchTotal, setSearchTotal] = useState(0)
    const [searchQuery, setSearchQuery] = useState('')
    const [semanticScores, setSemanticScores] = useState({})
    const LIMIT = 20

    const load = useCallback(async (reset = true) => {
        if (reset) { setLoading(true); setOffset(0) }
        else setLoadingMore(true)
        try {
            const { data } = await emailsApi.list({
                ...filter,
                limit: LIMIT,
                offset: reset ? 0 : offset + LIMIT,
            })
            setTotal(data.total || 0)
            if (reset) setEmails(data.items || [])
            else setEmails(prev => [...prev, ...(data.items || [])])
            if (!reset) setOffset(o => o + LIMIT)
        } catch { }
        setLoading(false)
        setLoadingMore(false)
    }, [filter, offset])

    useEffect(() => { if (!searchMode) load(true) }, [filter, searchMode])

    useEffect(() => {
        if (!searchMode) {
            const interval = setInterval(() => {
                emailsApi.list({ ...filter, limit: LIMIT, offset: 0 })
                    .then(({ data }) => {
                        setTotal(data.total || 0)
                        setEmails(data.items || [])
                    })
                    .catch(() => { })
            }, 10000)
            return () => clearInterval(interval)
        }
    }, [filter, searchMode])

    const handleSearchResults = useCallback((items, total, query) => {
        setSearchMode(true)
        setSearchResults(items)
        setSearchTotal(total)
        setSearchQuery(query)
        const scores = {}
        items.forEach(e => { if (e.semantic_score) scores[e.gmail_id] = e.semantic_score })
        setSemanticScores(scores)
    }, [])

    const handleSearchClear = useCallback(() => {
        setSearchMode(false)
        setSearchResults([])
        setSemanticScores({})
        setSearchQuery('')
        load(true)
    }, [load])

    const handleSelect = useCallback(async (email) => {
        setLoadingDetail(true)
        setProcessError(null)
        setReplyDraft(null)
        setEditedReply('')
        setUseAlt(false)
        setSentSuccess(false)
        setEmailDeadlines([])
        try {
            const { data } = await emailsApi.get(email.id)
            setSelected(data)
            setDetectingDeadlines(true)
            emailsApi.detectDeadlines(email.id)
                .then(res => setEmailDeadlines(res.data?.deadlines || []))
                .catch(() => { })
                .finally(() => setDetectingDeadlines(false))
        } catch {
            setSelected(email)
        }
        setLoadingDetail(false)
    }, [])

    const handleAddDeadlineToCalendar = async (dl, idx) => {
        setAddingDeadlineIdx(idx)
        try {
            await calendarApi.addFromEmail({
                email_id: selected?.id,
                title: dl.title,
                date: dl.date,
                time: dl.time,
                urgency: dl.urgency,
                type: dl.type,
                description: dl.description,
                email_subject: selected?.subject,
                email_sender: selected?.sender,
            })
            setEmailDeadlines(prev => prev.map((d, i) => i === idx ? { ...d, _added: true } : d))
        } catch {
            setProcessError('Failed to add deadline to calendar')
        }
        setAddingDeadlineIdx(null)
    }

    const handleGenerateReply = async () => {
        if (!selected) return
        setProcessing(selected.id)
        setProcessError(null)
        setReplyDraft(null)
        try {
            const { data } = await emailsApi.generateReply(selected.id)
            setReplyDraft(data)
            setEditedReply(data.main_reply || '')
            setUseAlt(false)
            if (data.warning) {
                setProcessError(data.warning)
            }
        } catch (err) {
            setProcessError(err?.response?.data?.detail || err.message || 'Reply generation failed')
        }
        setProcessing(null)
    }

    const handleSendReply = async () => {
        if (!selected || !replyDraft) return
        setSending(true)
        setProcessError(null)
        try {
            await emailsApi.sendReply(selected.id, {
                draft_id: replyDraft.draft_id,
                edited_text: editedReply !== replyDraft.main_reply ? editedReply : undefined,
            })
            setSentSuccess(true)
            setReplyDraft(null)
            load(true)
            const { data } = await emailsApi.get(selected.id)
            setSelected(data)
        } catch (err) {
            setProcessError(err?.response?.data?.detail || 'Failed to send reply')
        }
        setSending(false)
    }

    const handleRejectReply = async () => {
        if (!replyDraft) return
        try {
            await emailsApi.rejectReply(selected.id, { draft_id: replyDraft.draft_id })
        } catch { }
        setReplyDraft(null)
        setEditedReply('')
        setUseAlt(false)
    }

    const displayEmails = searchMode ? searchResults : emails
    const displayTotal = searchMode ? searchTotal : total
    const cls = selected ? CLASSIFICATIONS[selected.classification] || CLASSIFICATIONS.informational : null

    return (
        <div className="flex h-full" style={{ color: 'var(--text-primary)' }}>
            {/* ── Email List Panel ── */}
            <div className="w-[380px] flex-shrink-0 border-r flex flex-col" style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}>
                {/* Header */}
                <div className="px-4 pt-4 pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2.5">
                            <h1 className="text-lg font-bold text-white tracking-tight">Inbox</h1>
                            <span className="badge" style={{ background: 'rgba(99,102,241,0.1)', color: '#a5b4fc' }}>
                                {displayTotal} {searchMode ? 'results' : 'emails'}
                            </span>
                        </div>
                    </div>
                    <div className="flex gap-2 mb-2.5">
                        <select
                            className="flex-1 text-xs rounded-xl px-3 py-2 border outline-none transition-all"
                            style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                            value={filter.classification}
                            onChange={e => setFilter(f => ({ ...f, classification: e.target.value }))}
                        >
                            <option value="">All Types</option>
                            {Object.entries(CLASSIFICATIONS).map(([k, v]) => (
                                <option key={k} value={k}>{v.label}</option>
                            ))}
                        </select>
                        <select
                            className="flex-1 text-xs rounded-xl px-3 py-2 border outline-none transition-all"
                            style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                            value={filter.state}
                            onChange={e => setFilter(f => ({ ...f, state: e.target.value }))}
                        >
                            <option value="">All States</option>
                            <option value="open">Open</option>
                            <option value="waiting_response">Waiting</option>
                            <option value="resolved">Resolved</option>
                            <option value="follow_up_pending">Follow-up</option>
                        </select>
                    </div>
                    {!searchMode && (
                        <div className="flex items-center gap-2">
                            <SortAsc size={13} style={{ color: 'var(--text-muted)' }} />
                            <select
                                className="flex-1 text-xs rounded-xl px-3 py-2 border outline-none transition-all"
                                style={{ background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}
                                value={filter.sort_by}
                                onChange={e => setFilter(f => ({ ...f, sort_by: e.target.value }))}
                            >
                                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                            </select>
                        </div>
                    )}
                </div>

                <SearchBar onResults={handleSearchResults} onClear={handleSearchClear} />

                {/* Email list */}
                <div className="flex-1 overflow-auto">
                    {loading && <EmailSkeleton />}
                    {!loading && displayEmails.length === 0 && (
                        <div className="p-8 text-center">
                            <Mail size={36} style={{ margin: '0 auto 12px', opacity: 0.15, color: 'var(--text-muted)' }} />
                            <p className="text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
                                {searchMode ? 'No results found' : 'No emails found'}
                            </p>
                        </div>
                    )}
                    {displayEmails.map((email, i) => (
                        <EmailItem
                            key={email.id}
                            email={email}
                            selected={selected}
                            onClick={handleSelect}
                            semanticScore={semanticScores[email.gmail_id]}
                        />
                    ))}
                    {!searchMode && emails.length < total && (
                        <button
                            onClick={() => load(false)}
                            disabled={loadingMore}
                            className="w-full py-3.5 text-xs font-medium transition-all hover:bg-white/[0.03]"
                            style={{ color: 'var(--text-muted)' }}
                        >
                            {loadingMore ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                                    Loading...
                                </span>
                            ) : `Load more (${total - emails.length} remaining)`}
                        </button>
                    )}
                </div>
            </div>

            {/* ── Detail Panel ── */}
            <div className="flex-1 overflow-auto" style={{ background: 'var(--bg-base)' }}>
                {!selected && !loadingDetail && (
                    <div className="h-full flex items-center justify-center">
                        <div className="text-center">
                            <div
                                className="w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-4"
                                style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.1)' }}
                            >
                                <Mail size={32} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                            </div>
                            <p className="font-semibold text-white mb-1">Select an email</p>
                            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Choose from the list to view details</p>
                        </div>
                    </div>
                )}

                {loadingDetail && (
                    <div className="h-full flex items-center justify-center">
                        <div className="flex flex-col items-center gap-3">
                            <div className="w-8 h-8 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
                            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Loading email...</span>
                        </div>
                    </div>
                )}

                {selected && cls && !loadingDetail && (
                    <motion.div
                        className="p-6 max-w-4xl"
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                    >
                        {/* ── Email Header Card ── */}
                        <div className="glass-card-elevated p-6 mb-5">
                            <div className="flex items-start gap-4 mb-4">
                                <SenderAvatar name={selected.sender_name || selected.sender} size={48} />
                                <div className="flex-1 min-w-0">
                                    <h2 className="text-xl font-bold text-white mb-1 leading-tight">{selected.subject || '(No subject)'}</h2>
                                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                                        <span className="text-white font-medium">{selected.sender_name || selected.sender}</span>
                                        <span style={{ color: 'var(--text-muted)' }}> &lt;{selected.sender}&gt;</span>
                                    </p>
                                    {selected.recipients && selected.recipients.length > 0 && (
                                        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                                            To: {selected.recipients.join(', ')}
                                        </p>
                                    )}
                                    {selected.cc && selected.cc.length > 0 && (
                                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                                            Cc: {selected.cc.join(', ')}
                                        </p>
                                    )}
                                    {selected.created_at && (
                                        <p className="text-xs mt-1" style={{ color: 'var(--text-faint)' }}>
                                            {new Date(selected.created_at).toLocaleString()}
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Badges */}
                            <div className="flex flex-wrap gap-2 mb-4">
                                <span className="badge" style={{ background: `${cls.color}15`, color: cls.color }}>
                                    <cls.icon size={11} /> {cls.label}
                                </span>
                                <span className="badge" style={{ background: (STATES[selected.state] || {}).bg, color: (STATES[selected.state] || {}).color }}>
                                    {(STATES[selected.state] || {}).label || selected.state?.replace('_', ' ')}
                                </span>
                                {selected.sentiment && (
                                    <span className="badge" style={{
                                        background: selected.sentiment === 'positive' ? 'rgba(16,185,129,0.12)' : selected.sentiment === 'negative' ? 'rgba(239,68,68,0.12)' : 'rgba(100,116,139,0.12)',
                                        color: selected.sentiment === 'positive' ? '#6ee7b7' : selected.sentiment === 'negative' ? '#fca5a5' : '#94a3b8',
                                    }}>
                                        {selected.sentiment}{selected.sentiment_tone ? ` · ${selected.sentiment_tone}` : ''}
                                    </span>
                                )}
                                {semanticScores[selected.gmail_id] && (
                                    <span className="badge" style={{ background: 'rgba(99,102,241,0.12)', color: '#a5b4fc' }}>
                                        {Math.round(semanticScores[selected.gmail_id] * 100)}% semantic match
                                    </span>
                                )}
                            </div>

                            {/* Priority */}
                            <div>
                                <p className="text-[11px] font-medium uppercase tracking-wider mb-1.5" style={{ color: 'var(--text-muted)' }}>Priority</p>
                                <PriorityBar score={selected.priority_score} />
                            </div>

                            {selected.attachment_summary && (
                                <div className="mt-4 p-3.5 rounded-xl text-sm" style={{ background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.1)' }}>
                                    <p className="font-medium mb-1 text-white">📎 Attachment Summary</p>
                                    <p style={{ color: 'var(--text-secondary)' }}>{selected.attachment_summary}</p>
                                </div>
                            )}
                        </div>

                        {/* ── Message Body ── */}
                        <div className="glass-card p-6 mb-5">
                            <h3 className="text-[11px] font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>Message</h3>
                            <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'var(--text-secondary)' }}>
                                {selected.body_text || selected.snippet || '(no body)'}
                            </div>
                        </div>

                        {/* ── Deadline Widget ── */}
                        {emailDeadlines.length > 0 && (
                            <motion.div
                                className="glass-card p-5 mb-5"
                                style={{ borderColor: 'rgba(245,158,11,0.2)' }}
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                            >
                                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                                    <Calendar size={15} style={{ color: '#f59e0b' }} />
                                    Deadlines Detected ({emailDeadlines.length})
                                </h3>
                                <div className="space-y-2.5">
                                    {emailDeadlines.map((dl, i) => {
                                        const urgColors = {
                                            critical: { color: '#ef4444', bg: 'rgba(239,68,68,0.08)', emoji: '🔴' },
                                            high: { color: '#f97316', bg: 'rgba(249,115,22,0.08)', emoji: '🟠' },
                                            medium: { color: '#eab308', bg: 'rgba(234,179,8,0.08)', emoji: '🟡' },
                                            low: { color: '#22c55e', bg: 'rgba(34,197,94,0.08)', emoji: '🟢' },
                                        }
                                        const u = urgColors[dl.urgency] || urgColors.medium
                                        const typeIcons = { submission: '📄', meeting: '🤝', exam: '📝', interview: '💼', payment: '💳', event: '🎯', reminder: '⏰', other: '📌' }
                                        return (
                                            <div key={i} className="p-3.5 rounded-xl border flex items-center gap-3 transition-all hover:border-opacity-60"
                                                style={{ background: u.bg, borderColor: `${u.color}22` }}>
                                                <div className="w-9 h-9 rounded-lg flex items-center justify-center text-lg" style={{ background: `${u.color}15` }}>
                                                    {typeIcons[dl.type] || '📌'}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <p className="text-sm font-medium text-white truncate">{dl.title}</p>
                                                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                                                        📅 {dl.date}{dl.time ? ` at ${dl.time}` : ''}
                                                        <span className="ml-2 badge" style={{ background: `${u.color}15`, color: u.color }}>
                                                            {u.emoji} {dl.urgency}
                                                        </span>
                                                    </p>
                                                    {dl.description && (
                                                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-faint)' }}>{dl.description}</p>
                                                    )}
                                                </div>
                                                {dl._added ? (
                                                    <span className="badge flex-shrink-0" style={{ background: 'rgba(16,185,129,0.12)', color: '#6ee7b7' }}>✓ Added</span>
                                                ) : (
                                                    <button
                                                        onClick={() => handleAddDeadlineToCalendar(dl, i)}
                                                        disabled={addingDeadlineIdx === i}
                                                        className="btn-ghost text-xs px-3 py-1.5 flex-shrink-0 font-medium"
                                                        style={{ color: '#fbbf24', borderColor: 'rgba(245,158,11,0.25)' }}
                                                    >
                                                        {addingDeadlineIdx === i ? (
                                                            <span className="w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin block" />
                                                        ) : (
                                                            <span className="flex items-center gap-1.5"><CalendarPlus size={12} /> Add</span>
                                                        )}
                                                    </button>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            </motion.div>
                        )}

                        {detectingDeadlines && (
                            <div className="flex items-center gap-2.5 mb-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                                <span className="w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
                                Scanning for deadlines...
                            </div>
                        )}

                        {/* ── Error Banner ── */}
                        {processError && (
                            <motion.div
                                className="rounded-xl p-3.5 mb-4 text-sm flex items-start gap-2.5"
                                style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#fca5a5' }}
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                            >
                                <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
                                {processError}
                            </motion.div>
                        )}

                        {/* ── AI Reply Generation Loading ── */}
                        {processing === selected.id && !replyDraft && (
                            <motion.div
                                className="glass-card p-5 mb-5"
                                style={{ borderColor: 'rgba(99,102,241,0.2)' }}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                            >
                                <div className="flex items-center gap-2 mb-4">
                                    <Sparkles size={14} style={{ color: '#818cf8' }} />
                                    <h3 className="text-sm font-semibold text-white">Generating Reply</h3>
                                </div>
                                <div className="space-y-2.5 mb-4">
                                    <div className="skeleton-line h-3 rounded w-full" />
                                    <div className="skeleton-line h-3 rounded w-11/12" />
                                    <div className="skeleton-line h-3 rounded w-4/5" />
                                    <div className="skeleton-line h-3 rounded w-3/5" />
                                </div>
                                <TypingIndicator />
                            </motion.div>
                        )}

                        {/* ── Reply Draft ── */}
                        {replyDraft && (
                            <motion.div
                                className="glass-card-elevated p-5 mb-5"
                                style={{ borderColor: 'rgba(99,102,241,0.2)' }}
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                            >
                                <div className="flex items-center justify-between mb-4">
                                    <div className="flex items-center gap-2.5">
                                        <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--gradient-accent)' }}>
                                            <Sparkles size={14} className="text-white" />
                                        </div>
                                        <h3 className="text-sm font-semibold text-white">AI Reply Draft</h3>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="badge" style={{
                                            background: replyDraft.confidence_score >= 0.7 ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)',
                                            color: replyDraft.confidence_score >= 0.7 ? '#6ee7b7' : '#fbbf24',
                                        }}>
                                            {Math.round((replyDraft.confidence_score || 0) * 100)}% confidence
                                        </span>
                                        {!useAlt && replyDraft.alternative_reply && (
                                            <button
                                                onClick={() => { setUseAlt(true); setEditedReply(replyDraft.alternative_reply) }}
                                                className="btn-ghost text-xs px-2.5 py-1"
                                                style={{ color: '#a5b4fc', borderColor: 'rgba(99,102,241,0.2)' }}
                                            >
                                                <RotateCcw size={11} className="inline mr-1" />
                                                Alternative
                                            </button>
                                        )}
                                        {useAlt && (
                                            <button
                                                onClick={() => { setUseAlt(false); setEditedReply(replyDraft.main_reply) }}
                                                className="btn-ghost text-xs px-2.5 py-1"
                                                style={{ color: '#a5b4fc', borderColor: 'rgba(99,102,241,0.2)' }}
                                            >
                                                Back to main
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {replyDraft.explanation && (
                                    <div className="text-xs mb-3 p-3 rounded-xl flex items-start gap-2" style={{ background: 'rgba(99,102,241,0.06)', color: 'var(--text-muted)' }}>
                                        <Sparkles size={12} className="flex-shrink-0 mt-0.5" style={{ color: '#818cf8' }} />
                                        {replyDraft.explanation}
                                    </div>
                                )}

                                {replyDraft.summary && (
                                    <p className="text-xs mb-3" style={{ color: 'var(--text-faint)' }}>
                                        <strong className="text-slate-400">Summary:</strong> {replyDraft.summary}
                                    </p>
                                )}

                                <textarea
                                    value={editedReply}
                                    onChange={e => setEditedReply(e.target.value)}
                                    rows={8}
                                    className="w-full rounded-xl p-4 text-sm outline-none resize-y border transition-all"
                                    style={{
                                        background: 'rgba(255,255,255,0.02)',
                                        borderColor: 'var(--border)',
                                        color: 'var(--text-primary)',
                                        lineHeight: 1.7,
                                    }}
                                />

                                {replyDraft.action_items && replyDraft.action_items.length > 0 && (
                                    <div className="mt-3.5 p-3.5 rounded-xl" style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.1)' }}>
                                        <p className="text-xs font-semibold mb-1.5" style={{ color: '#fbbf24' }}>📋 Action Items</p>
                                        <ul className="text-xs space-y-1" style={{ color: 'var(--text-secondary)' }}>
                                            {replyDraft.action_items.map((item, i) => (
                                                <li key={i} className="flex items-start gap-2">
                                                    <span style={{ color: '#818cf8' }}>•</span> {item}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                <div className="flex gap-2.5 mt-5">
                                    <button
                                        onClick={handleSendReply}
                                        disabled={sending}
                                        className="btn-success flex-1 py-2.5 text-sm flex items-center justify-center gap-2"
                                    >
                                        {sending ? (
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
                                        onClick={handleRejectReply}
                                        className="btn-danger-outline px-5 py-2.5 text-sm font-medium flex items-center gap-2"
                                    >
                                        <XCircle size={14} />
                                        Reject
                                    </button>
                                </div>

                                {sentSuccess && (
                                    <motion.div
                                        className="mt-3.5 rounded-xl p-3 text-sm flex items-center gap-2"
                                        style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: '#6ee7b7' }}
                                        initial={{ opacity: 0, scale: 0.95 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                    >
                                        ✅ Reply sent to {selected.sender}!
                                    </motion.div>
                                )}
                            </motion.div>
                        )}

                        {/* ── Action Buttons ── */}
                        {!replyDraft && !sentSuccess && selected.classification !== 'spam' && processing !== selected.id && (
                            <motion.div
                                className="flex gap-3"
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.15 }}
                            >
                                <button
                                    onClick={handleGenerateReply}
                                    disabled={processing === selected.id}
                                    className="btn-primary flex-1 py-3 text-sm flex items-center justify-center gap-2"
                                >
                                    <Sparkles size={15} />
                                    Generate AI Reply
                                </button>
                                <button
                                    onClick={() => handleAddDeadlineToCalendar({
                                        title: selected.subject || 'Follow up',
                                        date: new Date().toISOString().split('T')[0],
                                        time: '12:00',
                                        urgency: 'medium',
                                        type: 'event',
                                        description: 'Manually added from Inbox'
                                    }, 'manual')}
                                    disabled={addingDeadlineIdx === 'manual'}
                                    className="btn-ghost px-5 py-3 text-sm font-medium flex items-center gap-2"
                                    title="Add basic 30-min event for today to calendar"
                                >
                                    {addingDeadlineIdx === 'manual' ? (
                                        <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    ) : (
                                        <>
                                            <CalendarPlus size={15} />
                                            Add to Calendar
                                        </>
                                    )}
                                </button>
                            </motion.div>
                        )}
                    </motion.div>
                )}
            </div>
        </div>
    )
}
