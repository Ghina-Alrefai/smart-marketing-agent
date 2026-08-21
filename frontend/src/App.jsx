import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'react-hot-toast'

import AppLayout from './components/AppLayout'
import RequireAuth from './components/RequireAuth'
import LoginPage from './pages/LoginPage'
import Dashboard from './pages/Dashboard'
import ChatPage from './pages/ChatPage'
import ScheduledPage from './pages/ScheduledPage'
import BrandPage from './pages/BrandPage'
import ProductsPage from './pages/ProductsPage'
import CampaignsPage from './pages/CampaignsPage'
import NewCampaignPage from './pages/NewCampaignPage'
import CampaignDetailPage from './pages/CampaignDetailPage'
import SettingsPage from './pages/SettingsPage'
import IntelligencePage from './pages/IntelligencePage'
import UsersPage from './pages/UsersPage'
import MonitoringPage from './pages/MonitoringPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'brand', element: <BrandPage /> },
      { path: 'products', element: <ProductsPage /> },
      { path: 'campaigns', element: <CampaignsPage /> },
      { path: 'campaigns/new', element: <NewCampaignPage /> },
      { path: 'campaigns/:id', element: <CampaignDetailPage /> },
      { path: 'scheduled', element: <ScheduledPage /> },
      { path: 'intelligence', element: <IntelligencePage /> },
      { path: 'monitoring', element: <MonitoringPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'admin/users', element: <RequireAuth adminOnly><UsersPage /></RequireAuth> },
    ],
  },
])

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster position="top-center" toastOptions={{ duration: 3000 }} />
    </QueryClientProvider>
  )
}
