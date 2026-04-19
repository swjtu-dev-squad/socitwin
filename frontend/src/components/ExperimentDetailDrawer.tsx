import { useState, useEffect } from 'react'
import { X, Download, ChevronDown, ChevronUp } from 'lucide-react'
import { getExperimentResult, type ExperimentRunResult } from '../lib/experimentArchiveApi'

interface Props {
  experimentId: string | null
  onClose: () => void
}

export default function ExperimentDetailDrawer({ experimentId, onClose }: Props) {
  const [result, setResult] = useState<ExperimentRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    if (!experimentId) {
      setResult(null)
      return
    }
    setLoading(true)
    setError('')
    getExperimentResult(experimentId)
      .then(r => setResult(r))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [experimentId])

  if (!experimentId) return null

  const handleDownload = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${result.experimentId || experimentId}_result.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-gray-900 border-l border-gray-700 shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
        <h3 className="text-base font-semibold text-white">实验详情</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={!result}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors disabled:opacity-40"
          >
            <Download className="w-3 h-3" /> 导出 JSON
          </button>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {loading && (
          <div className="flex items-center justify-center h-32 text-gray-400">
            <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mr-2" />
            加载中...
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-3">
            <p className="text-sm text-red-300">{error}</p>
          </div>
        )}

        {result && !loading && (
          <>
            {/* Config */}
            <section>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                实验配置
              </h4>
              <div className="bg-gray-800 rounded-xl p-4 space-y-2">
                <InfoRow label="Experiment ID" value={result.experimentId} mono />
                <InfoRow label="名称" value={result.name} />
                <InfoRow label="数据集" value={result.datasetId} />
                <InfoRow label="平台" value={result.platform} />
                <InfoRow label="推荐器" value={result.recommenders?.join(', ')} />
                <InfoRow label="Steps" value={String(result.steps)} />
                <InfoRow label="Seed" value={String(result.seed)} />
              </div>
            </section>

            {/* Per-run metrics */}
            <section>
              <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                运行结果
              </h4>
              <div className="space-y-3">
                {result.runs?.map(run => (
                  <div key={run.recommender} className="bg-gray-800 rounded-xl p-4">
                    <p className="text-sm font-semibold text-blue-300 capitalize mb-3">
                      {run.recommender}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <MetricRow
                        label="极化指数 (final)"
                        value={run.metrics.polarization_final?.toFixed(6)}
                      />
                      <MetricRow
                        label="羊群指数 (final)"
                        value={run.metrics.herd_index_final?.toFixed(6)}
                      />
                      <MetricRow label="平均速度" value={run.metrics.velocity_avg?.toFixed(6)} />
                      <MetricRow label="总帖子数" value={String(run.metrics.total_posts)} />
                      <MetricRow label="活跃 Agents" value={String(run.metrics.unique_agents)} />
                      <MetricRow label="完成步数" value={String(run.metrics.steps_completed)} />
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Raw JSON toggle */}
            <section>
              <button
                onClick={() => setShowRaw(!showRaw)}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
              >
                {showRaw ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {showRaw ? '收起' : '查看'} 原始 JSON
              </button>
              {showRaw && (
                <pre className="mt-2 bg-gray-950 rounded-lg p-3 text-xs text-gray-300 overflow-auto max-h-64">
                  {JSON.stringify(result, null, 2)}
                </pre>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

function InfoRow({ label, value, mono }: { label: string; value?: string; mono?: boolean }) {
  return (
    <div className="flex justify-between items-start gap-2">
      <span className="text-xs text-gray-400 flex-shrink-0">{label}</span>
      <span
        className={`text-xs text-white text-right ${mono ? 'font-mono' : ''} truncate max-w-xs`}
      >
        {value || '—'}
      </span>
    </div>
  )
}

function MetricRow({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bg-gray-700/50 rounded p-2">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm text-white font-mono">{value ?? '—'}</p>
    </div>
  )
}
