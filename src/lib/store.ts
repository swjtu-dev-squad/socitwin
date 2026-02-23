import { create } from 'zustand';
import { SimulationStatus, LogEntry, GroupMessage, StatsHistoryEntry } from './types';

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
    currentStep: 0,
    activeAgents: 0,
    totalPosts: 0,
    polarization: 0,
    agents: [],
  },
  history: [],
  logs: [],
  groupMessages: [],

  setStatus: (status) => set((state) => {
    const newEntry = { ...status, timestamp: Date.now() };
    return { 
      status, 
      history: [...state.history, newEntry].slice(-100) 
    };
  }),
  addLog: (log) => set((state) => ({ logs: [log, ...state.logs].slice(0, 200) })),
  clearLogs: () => set({ logs: [] }),
  addGroupMessage: (msg) => set((state) => ({ groupMessages: [...state.groupMessages, msg].slice(-100) })),
  setRunning: (running) => set((state) => ({
    status: { ...state.status, running },
  })),
}));
