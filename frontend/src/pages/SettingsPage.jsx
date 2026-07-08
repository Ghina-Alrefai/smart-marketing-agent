import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { User } from 'lucide-react'
import useStore from '../store'
import { createUser } from '../api/client'

export default function SettingsPage() {
  const { user, setUser } = useStore()
  const [form, setForm] = useState({ name: user?.name || '', email: user?.email || '' })

  const mutation = useMutation({
    mutationFn: (data) => createUser(data),
    onSuccess: (res) => {
      setUser(res.data)
      toast.success('تم حفظ الإعدادات ✅')
    },
    onError: (err) => {
      if (err.response?.status === 409) toast.error('البريد الإلكتروني مسجل مسبقاً')
      else toast.error('حدث خطأ')
    },
  })

  return (
    <div className="p-8 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">الإعدادات</h1>
      <p className="text-gray-500 mb-8">معلومات حسابك</p>

      <div className="card space-y-4">
        <div className="flex items-center gap-4 mb-4">
          <div className="w-14 h-14 bg-primary-100 rounded-full flex items-center justify-center">
            <User size={24} className="text-primary-600" />
          </div>
          <div>
            <p className="font-bold text-gray-900">{user?.name || 'لم يتم الإعداد'}</p>
            <p className="text-sm text-gray-400">{user?.email || '—'}</p>
          </div>
        </div>

        <div>
          <label className="label">الاسم</label>
          <input className="input" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="اسمك الكامل" />
        </div>
        <div>
          <label className="label">البريد الإلكتروني</label>
          <input className="input" type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="example@email.com" dir="ltr" />
        </div>

        <button className="btn-primary w-full py-2.5" onClick={() => mutation.mutate(form)} disabled={!form.name || !form.email || mutation.isPending}>
          {mutation.isPending ? 'جاري الحفظ...' : user ? 'تحديث' : 'إنشاء حساب'}
        </button>
      </div>
    </div>
  )
}
