import { useState, useEffect } from 'react'
import { reportsApi } from '../api'
import ReactMarkdown from 'react-markdown'
import { RefreshCw, TrendingUp, AlertTriangle, Inbox, Clock } from 'lucide-react'
import { motion } from 'framer-motion'

function MetricCard({ label, value, color, icon: Icon }) {
    return (
        <motion.div
            className="glass-card p-4 group transition-all duration-200 hover:border-opacity-80"
            style={{ borderColor: `${color}15` }}
            whileHover={{ y: -2, boxShadow: `0 8px 24px ${color}15` }}
        >
            <div className="flex items-center justify-between mb-2">
                <p className="text-[11px] font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>{label}</p>
                {Icon && (
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: `${color}12` }}>
                        <Icon size={13} style={{ color }} />
                    </div>
                )}
            </div>
            <p className="text-2xl font-bold" style={{ color: color || 'white' }}>{value ?? '—'}</p>
        </motion.div>
    )
}

function ReportPanel({ type, generateFn, getFn }) {
    const [report, setReport] = useState(null)
    const [loading, setLoading] = useState(false)
    const [generating, setGenerating] = useState(false)

    const load = async () => {
        setLoading(true)
        try { const { data } = await getFn(); setReport(data) }
        catch { }
        setLoading(false)
    }

    useEffect(() => { load() }, [])

    const generate = async () => {
        setGenerating(true)
        try { const { data } = await generateFn(); setReport(data) }
        catch { alert('Generation failed') }
        setGenerating(false)
    }

    const m = report?.metrics || {}

    return (
        <div className="glass-card-elevated p-6">
            <div className="flex items-center justify-between mb-5">
                <h2 className="font-bold text-lg text-white capitalize">{type} Report</h2>
                <button
                    onClick={generate}
                    disabled={generating}
                    className="btn-primary flex items-center gap-2 px-4 py-2 text-sm"
                >
                    <RefreshCw size={13} className={generating ? 'animate-spin' : ''} />
                    {generating ? 'Generating...' : 'Generate'}
                </button>
            </div>

            {loading && (
                <div className="space-y-3 py-4">
                    <div className="skeleton-line h-3 rounded w-full" />
                    <div className="skeleton-line h-3 rounded w-11/12" />
                    <div className="skeleton-line h-3 rounded w-4/5" />
                </div>
            )}

            {report && report.metrics && (
                <div className="grid grid-cols-4 gap-3 mb-6">
                    <MetricCard label="Total Emails" value={m.total_emails} color="#6366f1" icon={Inbox} />
                    <MetricCard label="Urgent" value={m.urgent} color="#ef4444" icon={AlertTriangle} />
                    <MetricCard label="Open" value={m.open} color="#f59e0b" icon={Clock} />
                    <MetricCard label="Overdue Tasks" value={m.overdue_tasks} color="#8b5cf6" icon={TrendingUp} />
                </div>
            )}

            {report?.content_markdown ? (
                <div className="prose-custom text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                    <ReactMarkdown>{report.content_markdown}</ReactMarkdown>
                </div>
            ) : !loading ? (
                <div className="text-center py-12">
                    <div className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-3" style={{ background: 'rgba(99,102,241,0.06)' }}>
                        <TrendingUp size={24} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
                    </div>
                    <p className="font-medium text-white mb-1">No report yet</p>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Click Generate to create one</p>
                </div>
            ) : null}

            {report?.generated_at && (
                <p className="text-[11px] mt-4 pt-3 border-t" style={{ color: 'var(--text-faint)', borderColor: 'var(--border)' }}>
                    Generated: {new Date(report.generated_at).toLocaleString()}
                </p>
            )}
        </div>
    )
}

export default function Reports() {
    return (
        <div className="p-6">
            <div className="max-w-4xl mx-auto">
                <div className="mb-6">
                    <h1 className="text-2xl font-bold text-white tracking-tight">Intelligence Reports</h1>
                    <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>AI-generated summaries and insights</p>
                </div>
                <div className="space-y-6">
                    <ReportPanel type="daily" getFn={reportsApi.daily} generateFn={reportsApi.generateDaily} />
                    <ReportPanel type="weekly" getFn={reportsApi.weekly} generateFn={reportsApi.generateWeekly} />
                </div>
            </div>
        </div>
    )
}
