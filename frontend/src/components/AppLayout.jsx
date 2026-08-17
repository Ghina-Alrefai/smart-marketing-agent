import { useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import toast from 'react-hot-toast'
import { LayoutDashboard, Megaphone, Package, Sparkles, Settings, MessageCircle, CalendarClock, BrainCircuit } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import { getUser } from '../api/client'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'الرئيسية' },
  { to: '/chat', icon: MessageCircle, label: 'المساعد الذكي' },
  { to: '/brand', icon: Sparkles, label: 'البراند' },
  { to: '/products', icon: Package, label: 'المنتجات' },
  { to: '/campaigns', icon: Megaphone, label: 'الحملات' },
  { to: '/scheduled', icon: CalendarClock, label: 'المجدولة' },
  { to: '/intelligence', icon: BrainCircuit, label: 'الذكاء والتعلّم' },
  { to: '/settings', icon: Settings, label: 'الإعدادات' },
]

export default function AppLayout() {
  const { user, setUser, setActiveBrandId } = useStore()

  useEffect(() => {
    if (!user?.id) return undefined
    let cancelled = false

    getUser(user.id).catch((error) => {
      if (!cancelled && error.response?.status === 404) {
        setUser(null)
        setActiveBrandId(null)
        toast.error('بيانات المستخدم المحلية قديمة. أنشئ المستخدم من شاشة الإعدادات ثم أعد إنشاء البراند.')
      }
    })

    return () => { cancelled = true }
  }, [user?.id, setUser, setActiveBrandId])

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-l border-gray-100 flex flex-col shadow-sm flex-shrink-0">
        {/* Logo */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
              <Sparkles size={18} className="text-white" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm">AI Marketing OS</p>
              <p className="text-xs text-gray-400">نظام التسويق الذكي</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-all',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
