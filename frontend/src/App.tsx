import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './components/DashboardLayout'
import Overview from './pages/Overview'
import Agents from './pages/Agents'
import Logs from './pages/Logs'
import GroupChat from './pages/GroupChat'
import Profiles from './pages/Profiles'
import Experiments from './pages/Experiments'
import Settings from './pages/Settings'
import { Toaster } from 'sonner'

export default function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" theme="dark" richColors />
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route
          path="/overview"
          element={
            <DashboardLayout>
              <Overview />
            </DashboardLayout>
          }
        />
        <Route
          path="/profiles"
          element={
            <DashboardLayout>
              <Profiles />
            </DashboardLayout>
          }
        />
        <Route
          path="/agents"
          element={
            <DashboardLayout>
              <Agents />
            </DashboardLayout>
          }
        />
        <Route
          path="/logs"
          element={
            <DashboardLayout>
              <Logs />
            </DashboardLayout>
          }
        />
        <Route
          path="/groupchat"
          element={
            <DashboardLayout>
              <GroupChat />
            </DashboardLayout>
          }
        />
        <Route
          path="/experiments"
          element={
            <DashboardLayout>
              <Experiments />
            </DashboardLayout>
          }
        />
        <Route
          path="/settings"
          element={
            <DashboardLayout>
              <Settings />
            </DashboardLayout>
          }
        />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
