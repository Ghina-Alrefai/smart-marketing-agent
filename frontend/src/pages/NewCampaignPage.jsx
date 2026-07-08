import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Sparkles } from 'lucide-react'
import useStore from '../store'
import { createPlan, triggerGeneration, listBrands } from '../api/client'

const GOAL_SUGGESTIONS = [
  'زيادة المبيعات',
  'بناء الوعي بالعلامة التجارية',
  'زيادة التفاعل مع الجمهور',
  'الترويج لمنتج جديد',
  'بناء قاعدة متابعين',
  'تحفيز العملاء على الشراء المتكرر',
  'إطلاق عرض أو تخفيضات',
  'تعريف الجمهور بمنتجات محددة',
]

export default function NewCampaignPage() {
  const { user } = useStore()
  const navigate = useNavigate()

  const { data: brands = [] } = useQuery({
    queryKey: ['brands', user?.id],
    queryFn: () => listBrands(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const [form, setForm] = useState({
    campaign_name: '',
    brand_id: '',
    days: 7,
    platform: 'facebook',
    campaign_goal: '',
  })

  const mutation = useMutation({
    mutationFn: async (data) => {
      const planRes = await createPlan(user.id, data)
      const planId = planRes.data.id
      await triggerGeneration(planId)
      return planId
    },
    onSuccess: (planId) => {
      toast.success('بدأ التوليد! 🚀')
      navigate(`/campaigns/${planId}`)
    },
    onError: () => toast.error('حدث خطأ'),
  })

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">حملة جديدة</h1>
      <p className="text-gray-500 mb-8">أخبرنا عن حملتك وسيتولى الذكاء الاصطناعي الباقي</p>

      <div className="card space-y-5">
        <div>
          <label className="label">اسم الحملة</label>
          <input className="input" value={form.campaign_name} onChange={e => setForm(f => ({ ...f, campaign_name: e.target.value }))} placeholder="مثال: حملة رمضان 2025" />
        </div>

        <div>
          <label className="label">البراند *</label>
          <select className="input" value={form.brand_id} onChange={e => setForm(f => ({ ...f, brand_id: parseInt(e.target.value) }))}>
            <option value="">اختر البراند</option>
            {brands.map(b => <option key={b.id} value={b.id}>{b.brand_name}</option>)}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">عدد الأيام</label>
            <select className="input" value={form.days} onChange={e => setForm(f => ({ ...f, days: parseInt(e.target.value) }))}>
              {[3, 5, 7, 10, 14, 30].map(d => <option key={d} value={d}>{d} أيام</option>)}
            </select>
          </div>
          <div>
            <label className="label">المنصة</label>
            <select className="input" value={form.platform} onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}>
              <option value="facebook">Facebook</option>
              <option value="instagram">Instagram</option>
            </select>
          </div>
        </div>

        {/* Campaign goal with suggestions */}
        <div>
          <label className="label">هدف الحملة</label>
          <input
            className="input mb-3"
            value={form.campaign_goal}
            onChange={e => setForm(f => ({ ...f, campaign_goal: e.target.value }))}
            placeholder="اكتب هدفاً أو اختر من المقترحات أدناه..."
          />
          <div className="flex flex-wrap gap-2">
            {GOAL_SUGGESTIONS.map(g => (
              <button key={g} type="button"
                onClick={() => setForm(f => ({ ...f, campaign_goal: g }))}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all
                  ${form.campaign_goal === g
                    ? 'bg-primary-600 text-white border-primary-600'
                    : 'border-gray-200 text-gray-600 hover:border-primary-300 hover:bg-gray-50'}`}>
                {g}
              </button>
            ))}
          </div>
        </div>

        <button
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
          onClick={() => mutation.mutate(form)}
          disabled={!form.brand_id || !form.campaign_goal || mutation.isPending}
        >
          <Sparkles size={20} />
          {mutation.isPending ? 'جاري الإنشاء...' : 'ابدأ التوليد بالذكاء الاصطناعي'}
        </button>
      </div>
    </div>
  )
}
