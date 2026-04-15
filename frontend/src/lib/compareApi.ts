// R6 Compare API client
import type { ExperimentRunResult } from './experimentApi'

export interface CompareSelection {
  experimentId?: string
  runA?: string
  runB?: string
}

export interface CompareMetrics {
  recommender: string
  polarization_final: number
  herd_index_final: number
  velocity_avg: number
  total_posts: number
  polarization_trace: number[]
  herd_trace: number[]
  velocity_trace: number[]
}

export interface CompareResult {
  runA: CompareMetrics
  runB: CompareMetrics
  diff: {
    polarization: number
    herd: number
    velocity: number
    posts: number
  }
}

export function extractCompareMetrics(
  result: ExperimentRunResult,
  recommender: string
): CompareMetrics | null {
  const run = result.runs?.find(r => r.recommender === recommender)
  if (!run) return null
  // Extract time-series from stepsTrace (preferred) or fallback to metrics arrays
  const stepsTrace = (run as any).stepsTrace || []
  const polarization_trace =
    stepsTrace.length > 0
      ? stepsTrace.map((s: any) => s.polarization)
      : run.metrics.polarization_trace || []
  const herd_trace =
    stepsTrace.length > 0 ? stepsTrace.map((s: any) => s.herd_index) : run.metrics.herd_trace || []
  const velocity_trace =
    stepsTrace.length > 0
      ? stepsTrace.map((s: any) => s.velocity)
      : run.metrics.velocity_trace || []
  return {
    recommender,
    polarization_final: run.metrics.polarization_final,
    herd_index_final: run.metrics.herd_index_final,
    velocity_avg: run.metrics.velocity_avg,
    total_posts: run.metrics.total_posts,
    polarization_trace,
    herd_trace,
    velocity_trace,
  }
}

export function buildCompareResult(a: CompareMetrics, b: CompareMetrics): CompareResult {
  return {
    runA: a,
    runB: b,
    diff: {
      polarization: b.polarization_final - a.polarization_final,
      herd: b.herd_index_final - a.herd_index_final,
      velocity: b.velocity_avg - a.velocity_avg,
      posts: b.total_posts - a.total_posts,
    },
  }
}
