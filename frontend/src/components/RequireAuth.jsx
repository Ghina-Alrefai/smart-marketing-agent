import { Navigate, useLocation } from 'react-router-dom'
import useStore from '../store'

/**
 * حارس المسارات: يمنع الوصول قبل تسجيل الدخول.
 * adminOnly=true → يسمح للمشرف فقط.
 */
export default function RequireAuth({ children, adminOnly = false }) {
  const location = useLocation()
  const token = useStore((s) => s.token)
  const user = useStore((s) => s.user)

  if (!token || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (adminOnly && user.role !== 'super_admin') {
    return <Navigate to="/" replace />
  }
  return children
}
