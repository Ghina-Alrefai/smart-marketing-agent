import { useNavigate } from 'react-router-dom'
import { User, ShieldCheck, LogOut, Mail, BadgeCheck } from 'lucide-react'
import useStore from '../store'
import { apiErrorMessage, createUser } from '../api/client'

export default function SettingsPage() {
  const navigate = useNavigate()
  const user = useStore((s) => s.user)
  const logout = useStore((s) => s.logout)
  const isAdmin = user?.role === 'super_admin'

  const handleLogout = () => { logout(); navigate('/login', { replace: true }) }

  return (
    <div className="p-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">الإعدادات</h1>
      <p className="text-gray-500 mb-8">معلومات حسابك</p>

      <div className="card space-y-5">
        <div className="flex items-center gap-4">
          {user?.avatar_url
            ? <img src={user.avatar_url} alt="" className="w-14 h-14 rounded-full" referrerPolicy="no-referrer" />
            : <div className="w-14 h-14 bg-primary-100 rounded-full flex items-center justify-center">
                <User size={24} className="text-primary-600" />
              </div>}
          <div>
            <p className="font-bold text-gray-900 flex items-center gap-1.5">
              {user?.name || 'مستخدم'}
              {isAdmin && <ShieldCheck size={15} className="text-amber-500" />}
            </p>
            <p className="text-sm text-gray-400" dir="ltr">{user?.email || '—'}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs text-gray-400 mb-1 flex items-center gap-1"><BadgeCheck size={13} /> الدور</p>
            <p className="text-sm font-semibold text-gray-800">{isAdmin ? 'مشرف (Super Admin)' : 'مستخدم عادي'}</p>
          </div>
          <div className="bg-gray-50 rounded-xl p-3">
            <p className="text-xs text-gray-400 mb-1 flex items-center gap-1"><Mail size={13} /> طريقة الدخول</p>
            <p className="text-sm font-semibold text-gray-800">{user?.auth_provider === 'google' ? 'Google' : 'كلمة مرور'}</p>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium
                     text-red-600 bg-red-50 hover:bg-red-100 transition-colors"
        >
          <LogOut size={16} /> تسجيل الخروج
        </button>
      </div>
    </div>
  )
}
