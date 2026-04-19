/**
 * Custom hooks for simulation data fetching
 *
 * Provides reusable hooks for fetching simulation data with proper error handling,
 * loading states, and automatic cleanup.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { simulationApi } from '@/lib/api';
import { normalizeSimulationStatus } from '@/lib/simulationStatus';
import type {
  SimulationStatus,
  TopicListItem,
  MetricsSummary,
  PropagationMetrics,
  PolarizationMetrics,
  HerdEffectMetrics,
  MetricsHistoryEntry,
  ChartDataPoint
} from '@/lib/types';
import { toast } from 'sonner';

/**
 * Hook to fetch and poll simulation status
 *
 * @param pollingInterval - Polling interval in milliseconds (default: 3000ms)
 * @returns Simulation status data with loading and error states
 */
export function useSimulationStatus(pollingInterval: number = 3000) {
  const [data, setData] = useState<SimulationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Use ref to track if component is mounted
  const isMountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await simulationApi.getStatus();

      // Only update state if component is still mounted
      if (isMountedRef.current) {
        const transformedData = normalizeSimulationStatus(response.data);

        setData(transformedData);
        setError(null);
      }
    } catch (err: any) {
      // Only update error state if component is still mounted
      if (isMountedRef.current) {
        const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch status');
        setError(error);
        console.error('Failed to fetch simulation status:', error);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchData();

    // Set up polling
    const intervalId = setInterval(fetchData, pollingInterval);

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchData, pollingInterval]);

  return { data, isLoading, error, refetch: fetchData };
}

/**
 * Hook to fetch available topics
 *
 * @returns Topics list with loading and error states
 */
export function useTopics(platform: string = 'twitter') {
  const [data, setData] = useState<TopicListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    setIsLoading(true)

    const normalizedPlatform = platform === 'twitter' || platform === 'reddit' ? platform : null

    const fetchTopics = async () => {
      if (!normalizedPlatform) {
        if (isMounted) {
          setData([])
          setError(null)
          setIsLoading(false)
        }
        return
      }

      try {
        const response = await simulationApi.getTopics({ platform: normalizedPlatform })

        if (isMounted) {
          if (response.data.success) {
            setData(response.data.topics)
            setError(null)
          } else {
            throw new Error((response.data as any)?.message || 'Failed to fetch topics')
          }
        }
      } catch (err: any) {
        if (isMounted) {
          const error =
            err instanceof Error ? err : new Error(err?.message || 'Failed to fetch topics')
          setError(error)
          setData([])
          toast.error('加载话题列表失败')
          console.error('Failed to fetch topics:', error)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchTopics()

    return () => {
      isMounted = false
    }
  }, [platform])

  return { data, isLoading, error }
}

/**
 * Hook to fetch and poll metrics summary
 *
 * @param pollingInterval - Polling interval in milliseconds (default: 5000ms)
 * @returns Metrics summary with loading and error states
 */
export function useMetricsSummary(pollingInterval: number = 5000) {
  const [data, setData] = useState<MetricsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    // Cancel previous request if still pending
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await simulationApi.getMetricsSummary();

      if (isMountedRef.current && !abortController.signal.aborted) {
        setData(response.data);
        setError(null);
      }
    } catch (err: any) {
      if (abortController.signal.aborted) {
        return;
      }

      if (isMountedRef.current) {
        const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch metrics');
        setError(error);
        // Don't show toast for polling errors
        console.error('Failed to fetch metrics summary:', error);
      }
    } finally {
      if (isMountedRef.current && !abortController.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    fetchData();

    const intervalId = setInterval(fetchData, pollingInterval);

    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData, pollingInterval]);

  return { data, isLoading, error, refetch: fetchData };
}

/**
 * Hook to fetch propagation metrics
 *
 * @param postId - Optional post ID for specific post analysis
 * @returns Propagation metrics with loading and error states
 */
export function usePropagationMetrics(postId?: number) {
  const [data, setData] = useState<PropagationMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchMetrics = async () => {
      try {
        const response = await simulationApi.getPropagationMetrics(postId);

        if (isMounted) {
          setData(response.data);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch propagation metrics');
          setError(error);
          console.error('Failed to fetch propagation metrics:', error);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchMetrics();

    return () => {
      isMounted = false;
    };
  }, [postId]);

  return { data, isLoading, error };
}

/**
 * Hook to fetch polarization metrics
 *
 * @param agentIds - Optional comma-separated list of agent IDs
 * @returns Polarization metrics with loading and error states
 */
export function usePolarizationMetrics(agentIds?: string) {
  const [data, setData] = useState<PolarizationMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchMetrics = async () => {
      try {
        const response = await simulationApi.getPolarizationMetrics(agentIds);

        if (isMounted) {
          setData(response.data);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch polarization metrics');
          setError(error);
          console.error('Failed to fetch polarization metrics:', error);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchMetrics();

    return () => {
      isMounted = false;
    };
  }, [agentIds]);

  return { data, isLoading, error };
}

/**
 * Hook to fetch herd effect metrics
 *
 * @param timeWindowSeconds - Optional time window in seconds
 * @returns Herd effect metrics with loading and error states
 */
export function useHerdEffectMetrics(timeWindowSeconds?: number) {
  const [data, setData] = useState<HerdEffectMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchMetrics = async () => {
      try {
        const response = await simulationApi.getHerdEffectMetrics(timeWindowSeconds);

        if (isMounted) {
          setData(response.data);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch herd effect metrics');
          setError(error);
          console.error('Failed to fetch herd effect metrics:', error);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchMetrics();

    return () => {
      isMounted = false;
    };
  }, [timeWindowSeconds]);

  return { data, isLoading, error };
}

/**
 * Derived hook: Get opinion distribution from polarization metrics
 *
 * This transforms the polarization metrics into an opinion distribution format
 * suitable for displaying in charts.
 *
 * @returns Opinion distribution array with loading and error states
 */
export function useOpinionDistribution() {
  const { data: polarizationData, isLoading, error } = usePolarizationMetrics();

  const [distribution, setDistribution] = useState<Array<{ name: string; value: number; count: number; color: string }>>([]);

  useEffect(() => {
    if (polarizationData?.agent_polarization) {
      // Map polarization directions to opinion categories
      const directionMap: Record<string, string> = {
        'EXTREME_CONSERVATIVE': 'Right',
        'MODERATE_CONSERVATIVE': 'Right',
        'NEUTRAL': 'Center',
        'MODERATE_PROGRESSIVE': 'Left',
        'EXTREME_PROGRESSIVE': 'Left',
      };

      const colorMap: Record<string, string> = {
        'Left': '#f43f5e',
        'Center': '#71717a',
        'Right': '#3b82f6'
      };

      const nameMap: Record<string, string> = {
        'Left': '极左',
        'Center': '中立',
        'Right': '极右'
      };

      // Count agents in each category
      const counts: Record<string, number> = { 'Left': 0, 'Center': 0, 'Right': 0 };
      polarizationData.agent_polarization.forEach(agent => {
        const category = directionMap[agent.direction] || 'Center';
        counts[category]++;
      });

      // Calculate percentages
      const total = polarizationData.agent_polarization.length;
      const newDistribution = Object.entries(counts).map(([category, count]) => ({
        name: nameMap[category] || category,
        value: total > 0 ? Math.round((count / total) * 100) : 0,
        count,
        color: colorMap[category] || '#71717a'
      }));

      setDistribution(newDistribution);
    }
  }, [polarizationData]);

  return { data: distribution, isLoading, error };
}

/**
 * Derived hook: Get herd index trend from herd effect metrics
 *
 * This transforms herd effect metrics into a trend format suitable for charts.
 *
 * @returns Herd index trend array with loading and error states
 */
export function useHerdIndexTrend() {
  const { data: herdData, isLoading, error } = useHerdEffectMetrics();

  const [trend, setTrend] = useState<Array<{ step: number; herdIndex: number }>>([]);

  useEffect(() => {
    if (herdData) {
      // For now, create a single data point from current metrics
      // In a real implementation, you might want to fetch historical data
      setTrend([{
        step: 0, // You would get this from the actual step number
        herdIndex: herdData.conformity_index
      }]);
    }
  }, [herdData]);

  return { data: trend, isLoading, error };
}

// ============================================================================
// Step-Driven Metrics Hooks (Phase 2: Step-Driven Architecture)
// ============================================================================

/**
 * Lightweight simulation status polling for state changes only
 *
 * This hook polls the simulation status at a specified interval, but only
 * to track state changes (running/paused/complete) and current step number.
 * It's designed to be lightweight and efficient for step-driven updates.
 *
 * @param pollingInterval - Polling interval in milliseconds (default: 2000ms)
 * @returns Simulation status data with current step and refetch function
 */
export function useSimulationStatusLightweight(pollingInterval: number = 2000) {
  const [data, setData] = useState<SimulationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);

  const isMountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await simulationApi.getStatus();

      if (isMountedRef.current) {
        const transformedData = normalizeSimulationStatus(response.data);
        const newStep = transformedData.currentStep || 0;

        setData(transformedData);
        setCurrentStep(newStep);
        setError(null);
      }
    } catch (err: any) {
      if (isMountedRef.current) {
        const error = err instanceof Error ? err : new Error(err?.message || 'Failed to fetch status');
        setError(error);
        console.error('Failed to fetch simulation status:', error);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    // Initial fetch
    fetchData();

    // Set up polling
    const intervalId = setInterval(fetchData, pollingInterval);

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      clearInterval(intervalId);
    };
  }, [fetchData, pollingInterval]);

  return { data, currentStep, isLoading, error, refetch: fetchData };
}

/**
 * Helper function to merge metrics by step_number
 *
 * Combines metrics from different types (propagation, polarization, herd_effect)
 * into a single chart data point array indexed by step number.
 *
 * @param propHistory - Propagation metrics history
 * @param polHistory - Polarization metrics history
 * @param herdHistory - Herd effect metrics history
 * @returns Merged chart data points sorted by step
 */
function mergeMetricsByStep(
  propHistory: MetricsHistoryEntry[],
  polHistory: MetricsHistoryEntry[],
  herdHistory: MetricsHistoryEntry[]
): ChartDataPoint[] {
  const stepMap = new Map<number, ChartDataPoint>();

  // Add propagation data
  propHistory.forEach(entry => {
    const metrics = entry.metric_data as PropagationMetrics;
    stepMap.set(entry.step_number, {
      step: entry.step_number,
      propagation: metrics.scale,
    });
  });

  // Add polarization data
  polHistory.forEach(entry => {
    const metrics = entry.metric_data as PolarizationMetrics;
    const existing = stepMap.get(entry.step_number) || { step: entry.step_number };
    stepMap.set(entry.step_number, {
      ...existing,
      polarization: metrics.average_magnitude,
    });
  });

  // Add herd effect data
  herdHistory.forEach(entry => {
    const metrics = entry.metric_data as HerdEffectMetrics;
    const existing = stepMap.get(entry.step_number) || { step: entry.step_number };
    stepMap.set(entry.step_number, {
      ...existing,
      herdEffect: metrics.conformity_index,
    });
  });

  // Convert to array and sort by step
  return Array.from(stepMap.values())
    .filter(point => point.polarization !== undefined || point.propagation !== undefined || point.herdEffect !== undefined)
    .sort((a, b) => a.step - b.step);
}

/**
 * Load complete metrics history from database
 *
 * This hook fetches all historical metrics data from the database.
 * It refetches data when currentStep changes to show latest data.
 *
 * @param currentStep - Current simulation step number (triggers refetch when changed)
 * @returns Metrics history array with loading and error states
 */
export function useMetricsHistory(currentStep?: number) {
  const [data, setData] = useState<ChartDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    let isMounted = true;

    const fetchHistory = async () => {
      try {
        // Fetch history for all three metric types in parallel
        const [propHistory, polHistory, herdHistory] = await Promise.all([
          simulationApi.getMetricsHistory({ metric_type: 'propagation', limit: 1000 }),
          simulationApi.getMetricsHistory({ metric_type: 'polarization', limit: 1000 }),
          simulationApi.getMetricsHistory({ metric_type: 'herd_effect', limit: 1000 }),
        ]);

        if (isMounted && isMountedRef.current) {
          // Merge by step_number - cast to correct type
          const mergedData = mergeMetricsByStep(
            propHistory.data.history as MetricsHistoryEntry[],
            polHistory.data.history as MetricsHistoryEntry[],
            herdHistory.data.history as MetricsHistoryEntry[]
          );

          setData(mergedData);
          setError(null);
        }
      } catch (err: any) {
        if (isMounted && isMountedRef.current) {
          const error = err instanceof Error ? err : new Error('Failed to fetch metrics history');
          setError(error);
          toast.error('加载指标历史失败');
          console.error('Failed to fetch metrics history:', error);
        }
      } finally {
        if (isMounted && isMountedRef.current) {
          setIsLoading(false);
        }
      }
    };

    fetchHistory();

    return () => {
      isMounted = false;
    };
  }, [currentStep]); // 添加 currentStep 作为依赖，当 step 变化时重新获取

  return { data, isLoading, error, refetch: () => { /* TODO: Implement refetch if needed */ } };
}

/**
 * Step-driven metrics fetching
 *
 * This hook watches the current step number and only fetches new metrics
 * when the step increases. This eliminates unnecessary API calls when
 * the simulation is paused or not progressing.
 *
 * @param currentStep - Current simulation step number
 * @returns Latest metrics with loading state and last fetched step
 */
export function useStepDrivenMetrics(currentStep: number) {
  const [latestMetrics, setLatestMetrics] = useState<{
    propagation: PropagationMetrics | null;
    polarization: PolarizationMetrics | null;
    herdEffect: HerdEffectMetrics | null;
  }>({
    propagation: null,
    polarization: null,
    herdEffect: null,
  });

  const [lastFetchedStep, setLastFetchedStep] = useState<number>(-1);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Only fetch if step has increased (or if we haven't fetched any data yet)
    if (currentStep <= lastFetchedStep && lastFetchedStep >= 0) {
      return;
    }

    const fetchNewMetrics = async () => {
      setIsLoading(true);
      try {
        // Fetch latest metrics for all types in parallel
        const [prop, pol, herd] = await Promise.all([
          simulationApi.getLatestMetrics('propagation').catch(() => null),
          simulationApi.getLatestMetrics('polarization').catch(() => null),
          simulationApi.getLatestMetrics('herd_effect').catch(() => null),
        ]);

        setLatestMetrics({
          propagation: prop?.data || null,
          polarization: pol?.data || null,
          herdEffect: herd?.data || null,
        });

        setLastFetchedStep(currentStep);
      } catch (err) {
        console.error('Failed to fetch new metrics:', err);
        // Don't show toast for step-driven errors to avoid spam
      } finally {
        setIsLoading(false);
      }
    };

    fetchNewMetrics();
  }, [currentStep, lastFetchedStep]);

  return { latestMetrics, isLoading, lastFetchedStep };
}
