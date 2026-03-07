import { create } from 'zustand';
import { SimulationStatus, LogEntry, GroupMessage, StatsHistoryEntry } from './types';

// LocalStorage 持久化键名
const LOGS_STORAGE_KEY = 'oasis_simulation_logs';
const MAX_STORED_LOGS = 500; // localStorage 最多保存 500 条

// 从 localStorage 加载日志
const loadLogsFromStorage = (): LogEntry[] => {
  try {
    const stored = localStorage.getItem(LOGS_STORAGE_KEY);
    if (stored) {
      const logs = JSON.parse(stored) as LogEntry[];
      console.log(`✅ 从 localStorage 加载了 ${logs.length} 条日志`);
      return logs;
    }
  } catch (error) {
    console.error('❌ 加载日志失败:', error);
  }
  return [];
};

// 保存日志到 localStorage
const saveLogsToStorage = (logs: LogEntry[]) => {
  try {
    localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(logs));
  } catch (error) {
    console.error('❌ 保存日志失败:', error);
  }
};

interface SimulationStore {
  status: SimulationStatus;
  history: StatsHistoryEntry[];
  logs: LogEntry[];
  groupMessages: GroupMessage[];
  setStatus: (status: SimulationStatus) => void;
  addLog: (log: LogEntry) => void;
  clearLogs: () => void;
  addGroupMessage: (msg: GroupMessage) => void;
  setRunning: (running: boolean) => void;
}

export const useSimulationStore = create<SimulationStore>((set) => ({
  status: {
    running: false,
    paused: false,
    currentStep: 0,
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0,
    agents: [],
  },
  history: [],
  logs: loadLogsFromStorage(), // 从 localStorage 加载
  groupMessages: [],

  setStatus: (status) => set((state) => {
    const newEntry = { ...status, timestamp: Date.now() };
    return {
      status,
      history: [...state.history, newEntry].slice(-100)
    };
  }),
  addLog: (log) => set((state) => {
    const newLogs = [log, ...state.logs].slice(0, MAX_STORED_LOGS);
    saveLogsToStorage(newLogs); // 保存到 localStorage
    return { logs: newLogs };
  }),
  clearLogs: () => {
    localStorage.removeItem(LOGS_STORAGE_KEY); // 清除 localStorage
    set({ logs: [] });
  },
  addGroupMessage: (msg) => set((state) => ({ groupMessages: [...state.groupMessages, msg].slice(-100) })),
  setRunning: (running) => set((state) => ({
    status: { ...state.status, running },
  })),
}));
