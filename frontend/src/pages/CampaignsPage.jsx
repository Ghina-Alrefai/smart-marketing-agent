import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus, Megaphone, Clock, CheckCircle, Loader, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import useStore from '../store'
import { listPlans, deletePlan } from '../api/client'

const STATUS_MAP = {
  pending: { label: 'في الانتظار', color: 'text-gray-500 bg-gray-100', icon: Clock },
  generating: { label: 'جاري التوليد', color: 'text-blue-600 bg-blue-50', icon: Loader },
  done: { label: 'مكتملة', color: 'text-emerald-600 bg-emerald-50', icon: CheckCircle },
  done_with_errors: { label: 'مكتملة مع أخطاء', color: 'text-amber-600 bg-amber-50', icon: CheckCircle },
  failed: { label: 'فشلت', color: 'text-red-600 bg-red-50', icon: Clock },
}

export default function CampaignsPage() {
  const { user } = useStore()
  const qc = useQueryClient()

  const { data: plans = [], isLoading } = useQuery({
    queryKey: ['plans', user?.id],
    queryFn: () => listPlans(user?.id).then(r => r.data),
    enabled: !!user?.id,
    refetchInterval: (query) => {
      const plans = query.state.data
      return Array.isArray(plans) && plans.some(p => p.status === 'generating') ? 3000 : false
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deletePlan,
    onSuccess: () => {
      qc.invalidateQueries(['plans'])
      toast.success('تم حذف الحملة')
    },
    onError: () => toast.error('فشل الحذف، حاولي مجدداً'),
  })

  const handleDelete = (e, planId) => {
    e.preventDefault()   // prevent Link navigation
    e.stopPropagation()
    if (window.confirm('هل أنتِ متأكدة من حذف هذه الحملة وجميع منشوراتها؟')) {
      deleteMutation.mutate(planId)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">الحملات</h1>
          <p className="text-gray-500">{plans.length} حملة</p>
        </div>
        <Link to="/campaigns/new" className="btn-primary flex items-center gap-2">
          <Plus size={18} />
          حملة جديدة
        </Link>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-20">جاري التحميل...</div>
      ) : plans.length === 0 ? (
        <div className="text-center py-20">
          <Megaphone size={48} className="mx-auto mb-4 text-gray-200" />
          <p className="text-gray-500 mb-4">لا توجد حملات بعد</p>
          <Link to="/campaigns/new" className="btn-primary inline-flex items-center gap-2">
            <Plus size={16} /> ابدأ حملتك الأولى
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {plans.map(plan => {
            const statusInfo = STATUS_MAP[plan.status] || STATUS_MAP.pending
            const StatusIcon = statusInfo.icon
            return (
              <Link key={plan.id} to={`/campaigns/${plan.id}`} className="card flex items-center justify-between hover:shadow-md transition-shadow group">
                <div>
                  <p className="font-semibold text-gray-900">{plan.campaign_name || `حملة #${plan.id}`}</p>
                  <p className="text-sm text-gray-400 mt-0.5">{plan.days} أيام · {plan.platform}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${statusInfo.color}`}>
                    <StatusIcon size={12} className={plan.status === 'generating' ? 'animate-spin' : ''} />
                    {statusInfo.label}
                  </span>
                  <button
                    onClick={(e) => handleDelete(e, plan.id)}
                    disabled={deleteMutation.isPending}
                    className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition-all"
                    title="حذف الحملة"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
