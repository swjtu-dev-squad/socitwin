import { io, Socket } from 'socket.io-client';
import { useSimulationStore } from './store';
import type { LogEntry, SimulationStatus, GroupMessage } from './types';

let socket: Socket | null = null;

export const initSocket = () => {
  if (socket) return socket;

  socket = io();

  socket.on('connect', () => {
    console.log('WebSocket connected');
  });

  socket.on('stats_update', (status: SimulationStatus) => {
    useSimulationStore.getState().setStatus(status);
  });

  socket.on('new_log', (log: LogEntry) => {
    useSimulationStore.getState().addLog(log);
  });

  socket.on('group_message', (msg: GroupMessage) => {
    useSimulationStore.getState().addGroupMessage(msg);
  });

  return socket;
};

export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
};
