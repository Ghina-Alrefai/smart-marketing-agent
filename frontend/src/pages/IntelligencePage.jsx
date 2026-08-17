import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  Activity, AlertTriangle, BrainCircuit, CheckCircle2, ChevronDown, ChevronUp,
  Database, Eye, FlaskConical, LockKeyhole, RefreshCw, ShieldCheck, Sparkles,
} from 'lucide-react'
import useStore from '../store'
import {
  activateMemoryPolicy,
  bootstrapBrandHistory,
  consolidateMemory,
  generateMemoryPolicies,
  getIntelligenceStatus,
  initializeIntelligence,
  listBrands,
  listMemoryPolicies,
} from '../api/client'

const STATUS_STYLE = {
  model_ready: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  cold_start: 'bg-amber-50 text-amber-700 border-amber-200',
  uninitialized: 'bg-gray-50 text-gray-600 border-gray-200',
}

const AGENT_LABELS = {
  CAMPAIGN_AGENT: 'وكيل الحملة',
  COPYWRITER_AGENT: 'وكيل كتابة المحتوى',
  DESIGNER_AGENT: 'وكيل التصميم',
  SCHEDULER_AGENT: 'وكيل الجدولة',
}

const POLICY_STATUS_LABELS = {
  draft: 'مسودة بانتظار المراجعة',
  active: 'نشطة',
  paused: 'متوقفة مؤقتاً',
  deprecated: 'قديمة',
  rejected: 'مرفوضة',
}

const FEATURE_LABELS = {
  campaign_goal: 'هدف الحملة',
  campaign_type: 'نوع الحملة',
  content_pillar: 'محور المحتوى',
  product_category: 'فئة المنتج',
  brand_name: 'اسم البراند',
  number_of_products: 'عدد المنتجات',
  is_product_post: 'هل المنشور خاص بمنتج؟',
  season: 'الموسم',
  writing_style: 'أسلوب الكتابة',
  tone: 'النبرة',
  hook_style: 'أسلوب الجملة الافتتاحية',
  cta_type: 'نوع الدعوة لاتخاذ إجراء',
  cta_presence: 'وجود دعوة لاتخاذ إجراء',
  number_of_ctas: 'عدد الدعوات لاتخاذ إجراء',
  dialect: 'اللهجة',
  language: 'اللغة',
  caption_length: 'طول النص',
  word_count: 'عدد الكلمات',
  emoji_count: 'عدد الرموز التعبيرية',
  number_of_hashtags: 'عدد الوسوم',
  text_similarity_to_success: 'تشابه النص مع المنشورات الناجحة',
  visual_style: 'الأسلوب البصري',
  layout_type: 'نوع التخطيط',
  dominant_colors: 'الألوان السائدة',
  text_in_image: 'النص داخل الصورة',
  contains_human: 'وجود شخص في الصورة',
  logo_position: 'موضع الشعار',
  image_count: 'عدد الصور',
  image_similarity_to_success: 'تشابه الصورة مع المنشورات الناجحة',
  day: 'يوم النشر',
  time_bucket: 'فترة النشر',
}

function displayValue(value) {
  if (value === null || value === undefined || value === '') return 'غير محددة'
  if (typeof value === 'boolean') return value ? 'نعم' : 'لا'
  if (Array.isArray(value)) return value.map(displayValue).join('، ')
  if (typeof value === 'object') {
    return Object.entries(value).map(([key, item]) => `${FEATURE_LABELS[key] || key}: ${displayValue(item)}`).join('، ')
  }
  return String(value)
}

function ruleDescription(rule) {
  const feature = FEATURE_LABELS[rule.feature_name] || rule.feature_name
  const value = displayValue(rule.feature_value)
  const description = rule.description || ''

  if (description.startsWith('Avoid ')) {
    return `يُنصح بتجنب «${feature}: ${value}» ما لم يطلبها موجز الحملة صراحةً. هذه توصية مرنة وليست قيداً إلزامياً.`
  }
  if (description.startsWith('Test approximately ')) {
    return `يُنصح باختبار قيمة تقارب «${value}» للخاصية «${feature}»، بشرط توافقها مع موجز الحملة وهوية البراند.`
  }
  if (description.startsWith('Prefer ')) {
    return `يُفضّل استخدام «${feature}: ${value}» عندما يتوافق ذلك مع موجز الحملة وهوية البراند.`
  }
  if (description.includes('warning signal')) {
    return `استخدم «${feature}» كإشارة تحذير لمراجعة المرشحين القريبين من نمط ضعيف سابقاً، وليس كسبب آلي للرفض.`
  }
  if (description.includes('soft ranking signal')) {
    return `استخدم «${feature}» كإشارة ترتيب مرنة لتفضيل المرشحين الأقرب إلى النمط الناجح تاريخياً دون نسخ المنشورات السابقة.`
  }
  return description || `راجع أثر الخاصية «${feature}» بالقيمة «${value}» قبل اعتماد السياسة.`
}

function confidenceStyle(value) {
  if (value >= 0.75) return 'bg-emerald-50 text-emerald-700'
  if (value >= 0.55) return 'bg-amber-50 text-amber-700'
  return 'bg-gray-100 text-gray-600'
}

function priorityLabel(priority) {
  return ({ 1: 'عالية جداً', 2: 'عالية', 3: 'متوسطة', 4: 'منخفضة', 5: 'استكشافية' })[priority] || `المستوى ${priority}`
}

function Metric({ label, value, note, icon: Icon }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-gray-400">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {note && <p className="text-xs text-gray-500 mt-1">{note}</p>}
        </div>
        <div className="w-10 h-10 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center">
          <Icon size={19}/>
        </div>
      </div>
    </div>
  )
}

export default function IntelligencePage() {
  const { user, activeBrandId, setActiveBrandId } = useStore()
  const qc = useQueryClient()
  const [openPolicyId, setOpenPolicyId] = useState(null)
  const { data: brands = [] } = useQuery({
    queryKey: ['brands', user?.id],
    queryFn: () => listBrands(user.id).then(r => r.data),
    enabled: !!user?.id,
  })

  useEffect(() => {
    if (!activeBrandId && brands[0]) setActiveBrandId(brands[0].id)
  }, [activeBrandId, brands, setActiveBrandId])

  const { data: status, isLoading, error } = useQuery({
    queryKey: ['intelligence-status', activeBrandId],
    queryFn: () => getIntelligenceStatus(activeBrandId).then(r => r.data),
    enabled: !!activeBrandId,
  })
  const { data: policies = [] } = useQuery({
    queryKey: ['memory-policies', activeBrandId],
    queryFn: () => listMemoryPolicies(activeBrandId).then(r => r.data),
    enabled: !!activeBrandId,
  })

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['intelligence-status', activeBrandId] })
    qc.invalidateQueries({ queryKey: ['memory-policies', activeBrandId] })
    qc.invalidateQueries({ queryKey: ['brands', user?.id] })
  }
  const useAction = (fn, success) => useMutation({
    mutationFn: fn,
    onSuccess: () => { refresh(); toast.success(success) },
    onError: (e) => toast.error(e?.response?.data?.detail || 'تعذر تنفيذ العملية'),
  })
  const initialize = useAction(() => initializeIntelligence(activeBrandId), 'تم تهيئة هوية البراند')
  const bootstrap = useAction(() => bootstrapBrandHistory(activeBrandId), 'تم استيراد الدليل التاريخي دون تكرار')
  const consolidate = useAction(() => consolidateMemory(activeBrandId), 'تم تجميع الدليل والتحقق من الأنماط')
  const draft = useAction(() => generateMemoryPolicies(activeBrandId), 'تم إنشاء سياسات مسودة؛ لم تُفعّل تلقائياً')
  const activate = useAction(
    ({ id }) => activateMemoryPolicy(id, user?.email || `user-${user?.id || 'unknown'}`),
    'تم تفعيل السياسة بموافقة بشرية',
  )

  useEffect(() => {
    setOpenPolicyId(null)
  }, [activeBrandId])

  const reviewAndActivate = (policy) => {
    const approved = window.confirm(
      `هل راجعت قواعد ${AGENT_LABELS[policy.target_agent] || policy.target_agent} وتريد اعتماد الإصدار ${policy.version} وتفعيله؟`,
    )
    if (approved) activate.mutate({ id: policy.id })
  }

  if (!user) return <div className="p-8 text-gray-500">أنشئ مستخدماً أولاً من الإعدادات.</div>
  if (!brands.length) return <div className="p-8 text-gray-500">أضف براند أولاً لتهيئة Brand DNA.</div>

  const model = status?.model_card || {}
  const memory = status?.memory || {}

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-primary-600 text-sm font-bold mb-1">
            <BrainCircuit size={18}/> طبقة الذكاء القابلة للتدقيق
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Brand DNA والذاكرة التكيفية</h1>
          <p className="text-sm text-gray-500 mt-1">الهوية ثابتة، والتعلّم تشغيلي ومحكوم بموافقة الإنسان.</p>
        </div>
        <select
          className="input max-w-xs"
          value={activeBrandId || ''}
          onChange={e => setActiveBrandId(Number(e.target.value))}
        >
          {brands.map(b => <option key={b.id} value={b.id}>{b.brand_name}</option>)}
        </select>
      </div>

      {isLoading && <div className="card text-gray-500 flex gap-2"><RefreshCw className="animate-spin" size={17}/> تحميل الحالة...</div>}
      {error && <div className="card text-red-600">تعذر تحميل حالة الذكاء.</div>}

      {status && <>
        <div className="card bg-gradient-to-l from-white to-primary-50/50">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-bold text-gray-900">{status.brand_name}</h2>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${STATUS_STYLE[status.dna_status] || STATUS_STYLE.uninitialized}`}>
                  {status.dna_status === 'model_ready' ? 'نموذج خاص بالصفحة' : status.dna_status === 'cold_start' ? 'Cold Start آمن' : 'غير مهيأ'}
                </span>
              </div>
              <p className="text-xs text-gray-500 mt-2 font-mono" dir="ltr">{status.dna_profile_version || 'No profile version yet'}</p>
            </div>
            <button className="btn-primary flex items-center gap-2" onClick={() => initialize.mutate()} disabled={initialize.isPending}>
              <Sparkles size={16}/> {status.dna_status === 'uninitialized' ? 'تهيئة الآن' : 'تحقق من التهيئة'}
            </button>
          </div>
          {status.cold_start && (
            <div className="mt-4 p-3 rounded-xl bg-amber-50 border border-amber-100 text-sm text-amber-800">
              لا نستخدم نموذج البراق لهذه الصفحة. المرشحون يمرّون بتحقق الهوية والبنية فقط، وتُحفظ النتائج لتدريب نموذج خاص لاحقاً.
            </div>
          )}
        </div>

        <div className="grid md:grid-cols-4 gap-4">
          <Metric label="منشورات التدريب" value={status.dna_training_post_count || 0} note="خاصة بالصفحة" icon={Database}/>
          <Metric label="ROC-AUC قبل التصميم" value={model.predesign_cv_metrics ? Number(model.predesign_cv_metrics.roc_auc).toFixed(3) : '—'} note="إشارة ترتيب لا ضمان" icon={Activity}/>
          <Metric label="الأدلة" value={memory.evidence_count || 0} note="خاصة بهذا البراند" icon={FlaskConical}/>
          <Metric label="السياسات النشطة" value={memory.active_policy_count || 0} note="بعد اعتماد بشري" icon={ShieldCheck}/>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="font-bold text-gray-900 flex items-center gap-2"><Database size={17} className="text-primary-600"/> دورة التعلّم المحكومة</h3>
            <p className="text-xs text-gray-500 mt-1">نفّذ المراحل بالترتيب. أي سياسة جديدة تبدأ كمسودة غير مؤثرة.</p>
            <div className="grid grid-cols-2 gap-3 mt-5">
              <button className="btn-secondary" onClick={() => bootstrap.mutate()} disabled={bootstrap.isPending || status.cold_start}>1. استيراد التاريخ</button>
              <button className="btn-secondary" onClick={() => consolidate.mutate()} disabled={consolidate.isPending}>2. تجميع وتحقق</button>
              <button className="btn-secondary col-span-2" onClick={() => draft.mutate()} disabled={draft.isPending}>3. إنشاء سياسات مسودة</button>
            </div>
            <div className="mt-4 p-3 rounded-xl bg-gray-50 text-xs text-gray-600 flex items-start gap-2">
              <LockKeyhole size={15} className="text-gray-500 mt-0.5 flex-shrink-0"/>
              لا يمكن للذاكرة تعديل Brand DNA، ولا يمكنها تفعيل سياسة أو نشر بوست تلقائياً.
            </div>
          </div>

          <div className="card">
            <h3 className="font-bold text-gray-900">ترتيب السلطة</h3>
            <ol className="mt-4 space-y-2">
              {(status.authority_order || []).map((item, i) => (
                <li key={item} className="flex items-center gap-3 text-sm text-gray-700">
                  <span className="w-6 h-6 rounded-full bg-primary-50 text-primary-700 flex items-center justify-center text-xs font-bold">{i + 1}</span>
                  {item.replaceAll('_', ' ')}
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="font-bold text-gray-900">سياسات الذاكرة</h3>
              <p className="text-xs text-gray-500 mt-1">فعّل المسودة فقط بعد مراجعة مصدرها وشروطها.</p>
            </div>
            <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full">{policies.length} سياسة</span>
          </div>
          <div className="mt-4 space-y-3">
            {!policies.length && <p className="text-sm text-gray-400 py-5 text-center">لا توجد سياسات بعد.</p>}
            {policies.map(policy => {
              const isOpen = openPolicyId === policy.id
              const panelId = `policy-details-${policy.id}`
              return (
                <div key={policy.id} className={`border rounded-xl overflow-hidden transition-colors ${isOpen ? 'border-primary-200 bg-primary-50/20' : 'border-gray-100 bg-white'}`}>
                  <button
                    type="button"
                    className="w-full p-4 flex flex-wrap items-center justify-between gap-3 text-right hover:bg-gray-50/70 transition-colors"
                    onClick={() => setOpenPolicyId(isOpen ? null : policy.id)}
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                  >
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-semibold text-sm text-gray-900">{AGENT_LABELS[policy.target_agent] || policy.target_agent}</span>
                        <span className="text-xs font-mono text-gray-400" dir="ltr">{policy.target_agent}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${policy.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                          {POLICY_STATUS_LABELS[policy.status] || policy.status}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1">الإصدار {policy.version} · {policy.rules.length} قواعد · {policy.source_insight_ids.length} مصادر</p>
                    </div>
                    <span className="flex items-center gap-2 text-sm font-semibold text-primary-700">
                      <Eye size={16}/> {isOpen ? 'إخفاء التفاصيل' : 'عرض القواعد ومراجعتها'}
                      {isOpen ? <ChevronUp size={17}/> : <ChevronDown size={17}/>} 
                    </span>
                  </button>

                  {isOpen && (
                    <div id={panelId} className="border-t border-primary-100 p-4 md:p-5 space-y-4">
                      <div className="flex items-start gap-2 rounded-xl bg-blue-50 border border-blue-100 p-3 text-sm text-blue-800">
                        <Eye size={17} className="mt-0.5 flex-shrink-0"/>
                        <p>راجع كل قاعدة ومصدرها. القواعد أدناه توصيات تشغيلية مرنة، ولا تتجاوز هوية البراند أو موجز الحملة.</p>
                      </div>

                      <div className="space-y-3">
                        {(policy.rules || []).map((rule, index) => (
                          <article key={rule.id || `${policy.id}-${index}`} className="rounded-xl border border-gray-200 bg-white p-4">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span className="w-7 h-7 rounded-full bg-primary-50 text-primary-700 flex items-center justify-center text-xs font-bold">{index + 1}</span>
                                <div>
                                  <h4 className="text-sm font-bold text-gray-900">{FEATURE_LABELS[rule.feature_name] || rule.feature_name}</h4>
                                  <p className="text-xs text-gray-400 font-mono mt-0.5" dir="ltr">{rule.feature_name}</p>
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-2 text-xs">
                                <span className={`px-2 py-1 rounded-full ${confidenceStyle(Number(rule.confidence_0_1 || 0))}`}>
                                  الثقة {Math.round(Number(rule.confidence_0_1 || 0) * 100)}٪
                                </span>
                                <span className="px-2 py-1 rounded-full bg-violet-50 text-violet-700">الأولوية: {priorityLabel(rule.priority)}</span>
                                <span className={`px-2 py-1 rounded-full ${rule.is_hard_constraint ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-600'}`}>
                                  {rule.is_hard_constraint ? 'قيد إلزامي' : 'توصية مرنة'}
                                </span>
                              </div>
                            </div>

                            <p className="mt-3 text-sm leading-7 text-gray-700">{ruleDescription(rule)}</p>

                            <dl className="mt-4 grid md:grid-cols-2 gap-3 text-sm">
                              <div className="rounded-lg bg-gray-50 p-3">
                                <dt className="text-xs font-semibold text-gray-400">القيمة المقترحة أو المرصودة</dt>
                                <dd className="mt-1 text-gray-800 break-words">{displayValue(rule.feature_value)}</dd>
                              </div>
                              <div className="rounded-lg bg-gray-50 p-3">
                                <dt className="text-xs font-semibold text-gray-400">شروط تطبيق القاعدة</dt>
                                <dd className="mt-1 text-gray-800 break-words">{Object.keys(rule.conditions || {}).length ? displayValue(rule.conditions) : 'تطبق بصورة عامة ضمن سياق البراند والحملة'}</dd>
                              </div>
                            </dl>

                            <div className="mt-3 text-xs text-gray-500">
                              <span className="font-semibold">مصدر الاستنتاج: </span>
                              <code className="font-mono break-all" dir="ltr">{rule.source_insight_id}</code>
                            </div>
                          </article>
                        ))}
                      </div>

                      {!policy.rules?.length && (
                        <div className="rounded-xl bg-amber-50 border border-amber-100 p-3 text-sm text-amber-800 flex items-start gap-2">
                          <AlertTriangle size={17} className="mt-0.5 flex-shrink-0"/> لا تحتوي هذه السياسة على قواعد قابلة للمراجعة، لذلك لا ينبغي تفعيلها.
                        </div>
                      )}

                      {policy.status === 'active' && (
                        <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-3 text-sm text-emerald-800 flex items-start gap-2">
                          <CheckCircle2 size={17} className="mt-0.5 flex-shrink-0"/>
                          <div>
                            <p className="font-semibold">هذه السياسة معتمدة ونشطة حالياً.</p>
                            {(policy.approved_by || policy.approved_at) && (
                              <p className="text-xs mt-1">اعتمدها {policy.approved_by || 'مستخدم مخوّل'}{policy.approved_at ? ` بتاريخ ${new Date(policy.approved_at).toLocaleString('ar')}` : ''}.</p>
                            )}
                          </div>
                        </div>
                      )}

                      {policy.status === 'draft' && (
                        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                          <p className="text-xs text-gray-500">لن تؤثر هذه السياسة في التوليد إلا بعد اعتمادك الصريح.</p>
                          <button
                            className="btn-primary text-sm flex items-center gap-1.5"
                            onClick={() => reviewAndActivate(policy)}
                            disabled={activate.isPending || !policy.rules?.length}
                          >
                            <CheckCircle2 size={15}/> راجعت القواعد — اعتماد وتفعيل
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </>}
    </div>
  )
}
