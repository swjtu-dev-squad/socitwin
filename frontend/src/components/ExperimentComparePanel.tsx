import { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, AlertCircle, RefreshCw } from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
} from 'recharts'
import {
  listExperiments,
  getExperimentResult,
  type ExperimentListItem,
  type ExperimentRunResult,
} from '../lib/experimentApi'
import { extractCompareMetrics, buildCompareResult, type CompareMetrics } from '../lib/compareApi'

const COLORS = { A: '#60a5fa', B: '#f472b6' }

export default function ExperimentComparePanel() {
  const [experiments, setExperiments] = useState<ExperimentListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [expA, setExpA] = useState('')
  const [expB, setExpB] = useState('')
  const [runA, setRunA] = useState('')
  const [runB, setRunB] = useState('')

  const [resultA, setResultA] = useState<ExperimentRunResult | null>(null)
  const [resultB, setResultB] = useState<ExperimentRunResult | null>(null)
  const [metricsA, setMetricsA] = useState<CompareMetrics | null>(null)
  const [metricsB, setMetricsB] = useState<CompareMetrics | null>(null)

  const fetchExperiments = async () => {
    setLoading(true)
    try {
      const list = await listExperiments()
      setExperiments(list)
      if (list.length >= 2) {
        setExpA(list[0].experimentId)
        setExpB(list[1].experimentId)
      } else if (list.length === 1) {
        setExpA(list[0].experimentId)
        setExpB(list[0].experimentId)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchExperiments()
  }, [])

  useEffect(() => {
    if (!expA) return
    getExperimentResult(expA)
      .then(r => {
        setResultA(r)
        const firstRec = r.runs?.[0]?.recommender || ''
        setRunA(firstRec)
      })
      .catch(() => setResultA(null))
  }, [expA])

  useEffect(() => {
    if (!expB) return
    getExperimentResult(expB)
      .then(r => {
        setResultB(r)
        const firstRec = r.runs?.[0]?.recommender || ''
        setRunB(firstRec)
      })
      .catch(() => setResultB(null))
  }, [expB])

  useEffect(() => {
    if (resultA && runA) setMetricsA(extractCompareMetrics(resultA, runA))
  }, [resultA, runA])

  useEffect(() => {
    if (resultB && runB) setMetricsB(extractCompareMetrics(resultB, runB))
  }, [resultB, runB])

  const compare = metricsA && metricsB ? buildCompareResult(metricsA, metricsB) : null

  // Build trace chart data
  const maxLen = Math.max(
    metricsA?.polarization_trace.length || 0,
    metricsB?.polarization_trace.length || 0
  )
  const traceData = Array.from({ length: maxLen }, (_, i) => ({
    step: i + 1,
    A_pol: metricsA?.polarization_trace[i] ?? null,
    B_pol: metricsB?.polarization_trace[i] ?? null,
    A_herd: metricsA?.herd_trace[i] ?? null,
    B_herd: metricsB?.herd_trace[i] ?? null,
  }))

  const barData = compare
    ? [
        {
          name: '极化指数',
          A: compare.runA.polarization_final,
          B: compare.runB.polarization_final,
        },
        { name: '羊群指数', A: compare.runA.herd_index_final, B: compare.runB.herd_index_final },
        { name: '平均速度', A: compare.runA.velocity_avg, B: compare.runB.velocity_avg },
      ]
    : []

  const radarData = compare
    ? [
        { metric: '极化', A: compare.runA.polarization_final, B: compare.runB.polarization_final },
        { metric: '羊群', A: compare.runA.herd_index_final, B: compare.runB.herd_index_final },
        { metric: '速度', A: compare.runA.velocity_avg, B: compare.runB.velocity_avg },
        { metric: '帖子/10', A: compare.runA.total_posts / 10, B: compare.runB.total_posts / 10 },
      ]
    : []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-purple-400" />
          实验对比面板
        </h2>
        <button
          onClick={fetchExperiments}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw className="w-3 h-3" /> 刷新
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 rounded-lg p-3">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {/* Run Selectors */}
      <div className="grid grid-cols-2 gap-4">
        {/* Run A */}
        <div className="bg-gray-800 rounded-xl p-4 border-l-4 border-blue-400">
          <p className="text-xs text-blue-400 font-semibold mb-2">Run A</p>
          <select
            value={expA}
            onChange={e => setExpA(e.target.value)}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 mb-2"
          >
            <option value="">— 选择实验 —</option>
            {experiments.map(e => (
              <option key={e.experimentId} value={e.experimentId}>
                {e.name}
              </option>
            ))}
          </select>
          {resultA && (
            <select
              value={runA}
              onChange={e => setRunA(e.target.value)}
              className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600"
            >
              {resultA.runs?.map(r => (
                <option key={r.recommender} value={r.recommender}>
                  {r.recommender}
                </option>
              ))}
            </select>
          )}
        </div>
        {/* Run B */}
        <div className="bg-gray-800 rounded-xl p-4 border-l-4 border-pink-400">
          <p className="text-xs text-pink-400 font-semibold mb-2">Run B</p>
          <select
            value={expB}
            onChange={e => setExpB(e.target.value)}
            className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600 mb-2"
          >
            <option value="">— 选择实验 —</option>
            {experiments.map(e => (
              <option key={e.experimentId} value={e.experimentId}>
                {e.name}
              </option>
            ))}
          </select>
          {resultB && (
            <select
              value={runB}
              onChange={e => setRunB(e.target.value)}
              className="w-full bg-gray-700 text-white rounded-lg px-3 py-2 text-sm border border-gray-600"
            >
              {resultB.runs?.map(r => (
                <option key={r.recommender} value={r.recommender}>
                  {r.recommender}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* No data placeholder */}
      {!compare && !loading && (
        <div className="flex flex-col items-center justify-center h-40 text-gray-500 bg-gray-800 rounded-xl">
          <TrendingUp className="w-10 h-10 mb-2 opacity-30" />
          <p className="text-sm">请先运行至少一个实验，然后选择两个 Run 进行对比</p>
        </div>
      )}

      {compare && (
        <>
          {/* Diff Summary Cards */}
          <div className="grid grid-cols-4 gap-3">
            <DiffCard
              label="极化差异"
              a={compare.runA.polarization_final}
              b={compare.runB.polarization_final}
            />
            <DiffCard
              label="羊群差异"
              a={compare.runA.herd_index_final}
              b={compare.runB.herd_index_final}
            />
            <DiffCard
              label="速度差异"
              a={compare.runA.velocity_avg}
              b={compare.runB.velocity_avg}
            />
            <DiffCard
              label="帖子差异"
              a={compare.runA.total_posts}
              b={compare.runB.total_posts}
              integer
            />
          </div>

          {/* Chart 1: Polarization Trace */}
          <div className="bg-gray-800 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">极化指数对比曲线</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={traceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="step" stroke="#6b7280" tick={{ fontSize: 11 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    background: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: 8,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="A_pol"
                  name={`A: ${metricsA?.recommender}`}
                  stroke={COLORS.A}
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="B_pol"
                  name={`B: ${metricsB?.recommender}`}
                  stroke={COLORS.B}
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 2: HerdIndex Trace */}
          <div className="bg-gray-800 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">羊群指数对比曲线</p>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={traceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="step" stroke="#6b7280" tick={{ fontSize: 11 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} domain={[0, 1]} />
                <Tooltip
                  contentStyle={{
                    background: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: 8,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="A_herd"
                  name={`A: ${metricsA?.recommender}`}
                  stroke={COLORS.A}
                  dot={false}
                  strokeWidth={2}
                />
                <Line
                  type="monotone"
                  dataKey="B_herd"
                  name={`B: ${metricsB?.recommender}`}
                  stroke={COLORS.B}
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 3: Bar Summary */}
          <div className="bg-gray-800 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">速度 / 指标柱状图对比</p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="name" stroke="#6b7280" tick={{ fontSize: 11 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    background: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: 8,
                  }}
                />
                <Legend />
                <Bar
                  dataKey="A"
                  name={`A: ${metricsA?.recommender}`}
                  fill={COLORS.A}
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="B"
                  name={`B: ${metricsB?.recommender}`}
                  fill={COLORS.B}
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Chart 4: Radar */}
          <div className="bg-gray-800 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-300 mb-3">综合雷达图</p>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#374151" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                <Radar
                  name={`A: ${metricsA?.recommender}`}
                  dataKey="A"
                  stroke={COLORS.A}
                  fill={COLORS.A}
                  fillOpacity={0.2}
                />
                <Radar
                  name={`B: ${metricsB?.recommender}`}
                  dataKey="B"
                  stroke={COLORS.B}
                  fill={COLORS.B}
                  fillOpacity={0.2}
                />
                <Legend />
                <Tooltip
                  contentStyle={{
                    background: '#1f2937',
                    border: '1px solid #374151',
                    borderRadius: 8,
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  )
}

function DiffCard({
  label,
  a,
  b,
  integer,
}: {
  label: string
  a: number
  b: number
  integer?: boolean
}) {
  const diff = b - a
  const isPos = diff > 0
  const fmt = (v: number) => (integer ? String(Math.round(v)) : v.toFixed(4))
  return (
    <div className="bg-gray-800 rounded-xl p-3">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <div className="flex items-end gap-1">
        <span className="text-sm text-blue-300 font-mono">{fmt(a)}</span>
        <span className="text-xs text-gray-500">→</span>
        <span className="text-sm text-pink-300 font-mono">{fmt(b)}</span>
      </div>
      <p className={`text-xs font-mono mt-1 ${isPos ? 'text-red-400' : 'text-green-400'}`}>
        {isPos ? '+' : ''}
        {fmt(diff)}
      </p>
    </div>
  )
}
