import { useQuery } from '@tanstack/react-query'
import { Users, ShieldCheck, Loader2, Mail, Clock } from 'lucide-react'
import { listAllUsers } from '../api/client'

const fmtDate = (s) => {
  if (!s) return '—'
  try { return new Date(s).toLocaleString('ar-EG', { dateStyle: 'medium', timeStyle: 'short' }) }
  catch { return s }
}

export default function UsersPage() {
  const { data: users, isLoading, isError } = useQuery({
    queryKey: ['all-users'],
    queryFn: () => listAllUsers().then((r) => r.data),
  })

  return (
    <div className="p-8">
      <div className="mb-8 flex items-center gap-3">
        <div className="w-11 h-11 bg-primary-50 rounded-xl flex items-center justify-center">
          <Users size={22} className="text-primary-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">المستخدمون المسجّلون</h1>
          <p className="text-gray-500 text-sm">لوحة المشرف — كل من سجّل دخوله للنظام</p>
        </div>
        {users && (
          <span className="ms-auto bg-primary-50 text-primary-700 text-sm font-bold px-3 py-1.5 rounded-lg">
            {users.length} مستخدم
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-gray-500"><Loader2 className="animate-spin" size={18} /> جارٍ التحميل…</div>
      )}
      {isError && <p className="text-red-500">تعذّر تحميل قائمة المستخدمين.</p>}

      {users && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-xs">
                  <th className="text-right font-semibold px-5 py-3">المستخدم</th>
                  <th className="text-right font-semibold px-5 py-3">البريد</th>
                  <th className="text-right font-semibold px-5 py-3">الدور</th>
                  <th className="text-right font-semibold px-5 py-3">طريقة الدخول</th>
                  <th className="text-right font-semibold px-5 py-3">آخر دخول</th>
                  <th className="text-right font-semibold px-5 py-3">التسجيل</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-50/60">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        {u.avatar_url
                          ? <img src={u.avatar_url} alt="" className="w-8 h-8 rounded-full" referrerPolicy="no-referrer" />
                          : <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-500 font-bold">{u.name?.[0] || '؟'}</div>}
                        <span className="font-medium text-gray-900">{u.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-gray-600" dir="ltr">
                      <span className="inline-flex items-center gap-1.5"><Mail size={13} className="text-gray-400" />{u.email}</span>
                    </td>
                    <td className="px-5 py-3">
                      {u.role === 'super_admin' ? (
                        <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-700 px-2.5 py-1 rounded-lg text-xs font-bold">
                          <ShieldCheck size={13} /> مشرف
                        </span>
                      ) : (
                        <span className="bg-gray-100 text-gray-600 px-2.5 py-1 rounded-lg text-xs">مستخدم</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-gray-500">{u.auth_provider === 'google' ? 'Google' : 'كلمة مرور'}</td>
                    <td className="px-5 py-3 text-gray-500">
                      <span className="inline-flex items-center gap-1.5"><Clock size={13} className="text-gray-400" />{fmtDate(u.last_login_at)}</span>
                    </td>
                    <td className="px-5 py-3 text-gray-500">{fmtDate(u.created_at)}</td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={6} className="px-5 py-10 text-center text-gray-400">لا يوجد مستخدمون بعد.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
