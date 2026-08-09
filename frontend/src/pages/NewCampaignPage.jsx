import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Sparkles, CalendarDays, Package, Check } from 'lucide-react'
import useStore from '../store'
import { createPlan, triggerGeneration, listBrands, listProducts, listEvents } from '../api/client'

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

const EVENT_TYPE_COLOR = {
  religious: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  sale: 'bg-rose-50 text-rose-700 border-rose-200',
  national: 'bg-blue-50 text-blue-700 border-blue-200',
  occasion: 'bg-purple-50 text-purple-700 border-purple-200',
  season: 'bg-amber-50 text-amber-700 border-amber-200',
  global: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  trend: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
}

// تاريخ اليوم بصيغة YYYY-MM-DD (افتراضي لبدء الحملة)
function todayISO() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export default function NewCampaignPage() {
  const { user } = useStore()
  const navigate = useNavigate()

  const { data: brands = [] } = useQuery({
    queryKey: ['brands', user?.id],
    queryFn: () => listBrands(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const { data: products = [] } = useQuery({
    queryKey: ['products', user?.id],
    queryFn: () => listProducts(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const [form, setForm] = useState({
    campaign_name: '',
    brand_id: '',
    days: 7,
    start_date: todayISO(),
    campaign_goals: [],
    product_ids: [],
    selected_events: [],
  })

  // المناسبات ضمن الفترة — تُجلب عند تحديد تاريخ البدء والمدة
  const { data: events = [], isFetching: eventsLoading } = useQuery({
    queryKey: ['events', form.start_date, form.days],
    queryFn: () => listEvents(form.start_date, form.days).then(r => r.data),
    enabled: !!form.start_date && !!form.days,
  })

  const toggle = (key, value) => setForm(f => {
    const arr = f[key]
    return { ...f, [key]: arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value] }
  })

  const toggleEvent = (ev) => setForm(f => {
    const exists = f.selected_events.some(e => e.id === ev.id)
    return {
      ...f,
      selected_events: exists
        ? f.selected_events.filter(e => e.id !== ev.id)
        : [...f.selected_events, ev],
    }
  })

  const mutation = useMutation({
    mutationFn: async (data) => {
      const payload = {
        ...data,
        // نبقي campaign_goal للتوافق الخلفي (أول هدف)
        campaign_goal: data.campaign_goals[0] || '',
      }
      const planRes = await createPlan(user.id, payload)
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

  const canSubmit = form.brand_id && form.campaign_goals.length > 0 && form.product_ids.length > 0 && !mutation.isPending

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">حملة جديدة</h1>
      <p className="text-gray-500 mb-8">أخبرنا عن حملتك وسيتولى الذكاء الاصطناعي الباقي</p>

      <div className="card space-y-6">
        <div>
          <label className="label">اسم الحملة</label>
          <input className="input" value={form.campaign_name} onChange={e => setForm(f => ({ ...f, campaign_name: e.target.value }))} placeholder="مثال: حملة رمضان 2026" />
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
            <label className="label">تاريخ بدء الحملة *</label>
            <input type="date" className="input" value={form.start_date}
              onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
          </div>
          <div>
            <label className="label">عدد الأيام</label>
            <select className="input" value={form.days} onChange={e => setForm(f => ({ ...f, days: parseInt(e.target.value) }))}>
              {[3, 5, 7, 10, 14, 30].map(d => <option key={d} value={d}>{d} أيام</option>)}
            </select>
          </div>
        </div>

        {/* اختيار المنتجات */}
        <div>
          <label className="label flex items-center gap-1.5">
            <Package size={15} /> المنتجات المشمولة بالحملة *
          </label>
          {products.length === 0 ? (
            <p className="text-sm text-gray-400 mt-1">لا توجد منتجات. أضيفي منتجات أولاً من صفحة المنتجات.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 mt-1">
              {products.map(p => {
                const active = form.product_ids.includes(p.id)
                return (
                  <button key={p.id} type="button" onClick={() => toggle('product_ids', p.id)}
                    className={`flex items-center gap-2 p-2 rounded-xl border text-right transition-all
                      ${active ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-primary-300'}`}>
                    {p.image_url
                      ? <img src={p.image_url} className="w-9 h-9 rounded-lg object-cover flex-shrink-0" />
                      : <div className="w-9 h-9 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0"><Package size={16} className="text-gray-300" /></div>}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{p.title}</p>
                      {p.is_marketed && <span className="text-[10px] text-amber-600">سبق تسويقه</span>}
                    </div>
                    {active && <Check size={16} className="text-primary-600 flex-shrink-0" />}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* أهداف الحملة — اختيار متعدد */}
        <div>
          <label className="label">أهداف الحملة * <span className="text-gray-400 font-normal">(يمكن اختيار أكثر من هدف)</span></label>
          <div className="flex flex-wrap gap-2">
            {GOAL_SUGGESTIONS.map(g => {
              const active = form.campaign_goals.includes(g)
              return (
                <button key={g} type="button" onClick={() => toggle('campaign_goals', g)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all
                    ${active ? 'bg-primary-600 text-white border-primary-600' : 'border-gray-200 text-gray-600 hover:border-primary-300 hover:bg-gray-50'}`}>
                  {g}
                </button>
              )
            })}
          </div>
        </div>

        {/* المناسبات ضمن مدة الحملة */}
        <div>
          <label className="label flex items-center gap-1.5">
            <CalendarDays size={15} /> مناسبات ضمن مدة الحملة
            <span className="text-gray-400 font-normal">(اختياري — تُدمج في المحتوى)</span>
          </label>
          {eventsLoading ? (
            <p className="text-sm text-gray-400 mt-1">جاري البحث عن المناسبات...</p>
          ) : events.length === 0 ? (
            <p className="text-sm text-gray-400 mt-1">لا توجد مناسبات معروفة ضمن هذه الفترة.</p>
          ) : (
            <div className="space-y-2 mt-1">
              {events.map(ev => {
                const active = form.selected_events.some(e => e.id === ev.id)
                return (
                  <button key={ev.id} type="button" onClick={() => toggleEvent(ev)}
                    className={`w-full flex items-center gap-3 p-2.5 rounded-xl border text-right transition-all
                      ${active ? 'border-primary-500 bg-primary-50' : 'border-gray-200 hover:border-primary-300'}`}>
                    <div className={`w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0
                      ${active ? 'bg-primary-600 border-primary-600' : 'border-gray-300'}`}>
                      {active && <Check size={13} className="text-white" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-gray-800 truncate">{ev.title}</p>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${EVENT_TYPE_COLOR[ev.type] || EVENT_TYPE_COLOR.occasion}`}>
                          {ev.type_label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 truncate">اليوم {ev.day_offset} · {ev.description}</p>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <button
          className="btn-primary w-full flex items-center justify-center gap-2 py-3 text-base"
          onClick={() => mutation.mutate(form)}
          disabled={!canSubmit}
        >
          <Sparkles size={20} />
          {mutation.isPending ? 'جاري الإنشاء...' : 'ابدأ التوليد بالذكاء الاصطناعي'}
        </button>
      </div>
    </div>
  )
}
