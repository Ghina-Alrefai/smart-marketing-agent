import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Sparkles, ShieldCheck, Loader2 } from 'lucide-react'
import useStore from '../store'
import { googleLogin, adminLogin } from '../api/client'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

// تحميل سكربت Google Identity Services مرة واحدة
function loadGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve()
    const existing = document.getElementById('google-gsi')
    if (existing) { existing.addEventListener('load', () => resolve()); return }
    const s = document.createElement('script')
    s.src = 'https://accounts.google.com/gsi/client'
    s.async = true; s.defer = true; s.id = 'google-gsi'
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('تعذّر تحميل Google Sign-In'))
    document.head.appendChild(s)
  })
}

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useStore((s) => s.login)
  const googleBtnRef = useRef(null)
  const [showAdmin, setShowAdmin] = useState(false)
  const [adminForm, setAdminForm] = useState({ email: '', password: '' })
  const [googleReady, setGoogleReady] = useState(false)

  const onAuthed = (res) => {
    login({ user: res.data.user, token: res.data.token })
    toast.success(`أهلاً ${res.data.user.name} 👋`)
    navigate(res.data.user.role === 'super_admin' ? '/admin/users' : '/', { replace: true })
  }

  const googleMut = useMutation({
    mutationFn: (credential) => googleLogin(credential),
    onSuccess: onAuthed,
    onError: (err) => toast.error(err.response?.data?.detail || 'فشل تسجيل الدخول عبر Google'),
  })

  const adminMut = useMutation({
    mutationFn: () => adminLogin(adminForm.email, adminForm.password),
    onSuccess: onAuthed,
    onError: (err) => toast.error(err.response?.data?.detail || 'بيانات الدخول غير صحيحة'),
  })

  // تهيئة زر Google الرسمي
  useEffect(() => {
    let cancelled = false
    if (!GOOGLE_CLIENT_ID) return
    loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id) return
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (resp) => resp?.credential && googleMut.mutate(resp.credential),
        })
        if (googleBtnRef.current) {
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: 'outline', size: 'large', shape: 'pill',
            text: 'signin_with', logo_alignment: 'center', width: 320,
          })
        }
        setGoogleReady(true)
      })
      .catch(() => toast.error('تعذّر تحميل Google Sign-In — تحقّق من الاتصال'))
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 via-white to-violet-50 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-14 h-14 bg-primary-600 rounded-2xl items-center justify-center mb-4 shadow-lg shadow-primary-600/20">
            <Sparkles size={26} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">AI Marketing OS</h1>
          <p className="text-gray-500 mt-1">نظام التسويق الذكي — سجّل الدخول للمتابعة</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl shadow-gray-200/60 border border-gray-100 p-8">
          {/* Google button */}
          <div className="flex flex-col items-center">
            {!GOOGLE_CLIENT_ID && (
              <p className="text-sm text-red-500 mb-3 text-center">
                لم يُضبط VITE_GOOGLE_CLIENT_ID
              </p>
            )}
            {googleMut.isPending ? (
              <div className="flex items-center gap-2 text-gray-500 py-3">
                <Loader2 className="animate-spin" size={18} /> جارٍ التحقق…
              </div>
            ) : (
              <div ref={googleBtnRef} className="min-h-[44px]" />
            )}
            {!googleReady && GOOGLE_CLIENT_ID && !googleMut.isPending && (
              <div className="flex items-center gap-2 text-gray-400 py-3 text-sm">
                <Loader2 className="animate-spin" size={16} /> تحميل Google…
              </div>
            )}
          </div>

          {/* Facebook — زر شكلي فقط (لا يقوم بأي إجراء) */}
          <button
            type="button"
            onClick={() => toast('تسجيل الدخول عبر فيسبوك غير مُفعّل حالياً', { icon: 'ℹ️' })}
            className="mt-3 w-full flex items-center justify-center gap-2.5 py-2.5 rounded-full
                       bg-[#1877F2] text-white font-medium text-sm hover:bg-[#166fe0] transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.79-4.69 4.53-4.69 1.31 0 2.68.24 2.68.24v2.97h-1.51c-1.49 0-1.96.93-1.96 1.89v2.25h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07z" />
            </svg>
            المتابعة عبر فيسبوك
          </button>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-gray-100" />
            <span className="text-xs text-gray-400">أو</span>
            <div className="flex-1 h-px bg-gray-100" />
          </div>

          {/* Admin login toggle */}
          <button
            type="button"
            onClick={() => setShowAdmin((v) => !v)}
            className="w-full flex items-center justify-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition-colors"
          >
            <ShieldCheck size={16} />
            دخول المشرف (Super Admin)
          </button>

          {showAdmin && (
            <form
              className="mt-4 space-y-3"
              onSubmit={(e) => { e.preventDefault(); adminMut.mutate() }}
            >
              <input
                className="input" type="email" dir="ltr" placeholder="admin@gmail.com"
                value={adminForm.email}
                onChange={(e) => setAdminForm((f) => ({ ...f, email: e.target.value }))}
              />
              <input
                className="input" type="password" dir="ltr" placeholder="كلمة المرور"
                value={adminForm.password}
                onChange={(e) => setAdminForm((f) => ({ ...f, password: e.target.value }))}
              />
              <button
                type="submit"
                disabled={adminMut.isPending || !adminForm.email || !adminForm.password}
                className="btn-primary w-full py-2.5 disabled:opacity-50"
              >
                {adminMut.isPending ? 'جارٍ الدخول…' : 'تسجيل دخول المشرف'}
              </button>
            </form>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          المستخدم العادي يسجّل عبر Google · المشرف عبر الحساب الثابت
        </p>
      </div>
    </div>
  )
}
