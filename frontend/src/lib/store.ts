import { create } from 'zustand'
import type { SimulationStatus, LogEntry, GroupMessage, StatsHistoryEntry } from './types'
import { normalizeSimulationStatus } from './simulationStatus'

// 清理旧的 LocalStorage 日志数据（一次性清理）
const OLD_LOGS_STORAGE_KEY = 'socitwin_simulation_logs'
if (typeof window !== 'undefined') {
  const oldLogs = localStorage.getItem(OLD_LOGS_STORAGE_KEY)
  if (oldLogs) {
    console.log('🧹 清理旧的 LocalStorage 日志数据')
    localStorage.removeItem(OLD_LOGS_STORAGE_KEY)
  }
}

interface SimulationStore {
  status: SimulationStatus
  history: StatsHistoryEntry[]
  logs: LogEntry[]
  groupMessages: GroupMessage[]

  // 单步执行进度状态
  stepProgress: { current: number; total: number; percentage: number }
  isStepping: boolean

  setStatus: (status: SimulationStatus) => void
  addLog: (log: LogEntry) => void
  clearLogs: () => void
  setLogs: (logs: LogEntry[]) => void
  addGroupMessage: (msg: GroupMessage) => void
  setRunning: (running: boolean) => void
  setStepProgress: (progress: { current: number; total: number; percentage: number }) => void
  setIsStepping: (stepping: boolean) => void
}

export const useSimulationStore = create<SimulationStore>(set => ({
  status: {
    state: 'uninitialized',
    running: false,
    paused: false,
    currentStep: 0,
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0,
    agents: [],
  },
  history: [],
  logs: [], // 不再从 localStorage 加载，初始为空
  groupMessages: [],

  // 单步执行进度状态初始化
  stepProgress: { current: 0, total: 0, percentage: 0 },
  isStepping: false,

  setStatus: status =>
    set(state => {
      const normalized = normalizeSimulationStatus(status)
      const newEntry = { ...normalized, timestamp: Date.now() }
      return {
        status: normalized,
        history: [...state.history, newEntry].slice(-100),
      }
    }),
  addLog: log =>
    set(state => {
      const newLogs = [log, ...state.logs]
      return { logs: newLogs }
    }),
  clearLogs: () => {
    set({ logs: [] })
  },
  setLogs: logs => set({ logs }), // 新增：从数据库加载日志时使用
  addGroupMessage: msg =>
    set(state => ({ groupMessages: [...state.groupMessages, msg].slice(-100) })),
  setRunning: running =>
    set(state => ({
      status: { ...state.status, running },
    })),
  setStepProgress: progress => set({ stepProgress: progress }),
  setIsStepping: stepping => set({ isStepping: stepping }),
}))
