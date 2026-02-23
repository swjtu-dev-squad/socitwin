import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { initSocket, disconnectSocket } from './lib/socket';
import DashboardLayout from './components/DashboardLayout';
import Overview from './pages/Overview';
import Control from './pages/Control';
import Profiles from './pages/Profiles';
import Agents from './pages/Agents';
import Logs from './pages/Logs';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import GroupChat from './pages/GroupChat';
import { Toaster } from 'sonner';

export default function App() {
  useEffect(() => {
    initSocket();
    return () => disconnectSocket();
  }, []);

  return (
    <BrowserRouter>
      <Toaster position="top-right" theme="dark" richColors />
      <DashboardLayout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/control" element={<Control />} />
          <Route path="/profiles" element={<Profiles />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/groupchat" element={<GroupChat />} />
        </Routes>
      </DashboardLayout>
    </BrowserRouter>
  );
}
