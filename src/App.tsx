import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { initSocket, disconnectSocket } from './lib/socket';
import DashboardLayout from './components/DashboardLayout';
import Home from './pages/Home';
import Overview from './pages/Overview';
import Profiles from './pages/Profiles';
import Agents from './pages/Agents';
import Logs from './pages/Logs';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import GroupChat from './pages/GroupChat';
import Experiments from './pages/Experiments';
import { Toaster } from 'sonner';

export default function App() {
  useEffect(() => {
    initSocket();
    return () => disconnectSocket();
  }, []);

  return (
    <BrowserRouter>
      <Toaster position="top-right" theme="dark" richColors />
      <Routes>
        {/* Landing page without dashboard layout */}
        <Route path="/" element={<Home />} />

        {/* Dashboard pages with layout */}
        <Route path="/overview" element={
          <DashboardLayout>
            <Overview />
          </DashboardLayout>
        } />
        <Route path="/profiles" element={
          <DashboardLayout>
            <Profiles />
          </DashboardLayout>
        } />
        <Route path="/agents" element={
          <DashboardLayout>
            <Agents />
          </DashboardLayout>
        } />
        <Route path="/logs" element={
          <DashboardLayout>
            <Logs />
          </DashboardLayout>
        } />
        <Route path="/analytics" element={
          <DashboardLayout>
            <Analytics />
          </DashboardLayout>
        } />
        <Route path="/settings" element={
          <DashboardLayout>
            <Settings />
          </DashboardLayout>
        } />
        <Route path="/groupchat" element={
          <DashboardLayout>
            <GroupChat />
          </DashboardLayout>
        } />
        <Route path="/experiments" element={
          <DashboardLayout>
            <Experiments />
          </DashboardLayout>
        } />
      </Routes>
    </BrowserRouter>
  );
}
