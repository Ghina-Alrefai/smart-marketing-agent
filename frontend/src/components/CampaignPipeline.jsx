import { Check, Loader, AlertTriangle } from 'lucide-react'

/**
 * خط أنابيب توليد الحملة — يعرض الوكلاء الستة كعُقد متسلسلة،
 * ويُبرز الوكيل العامل حالياً مع شرح ما يفعله.
 *
 * المصدر الوحيد للحقيقة هو plan.current_stage القادم من الخادم
 * (نفس النصوص التي يبثّها campaign_pipeline.py عبر emit).
 */

// الترتيب هنا يطابق مراحل emit() في workflows/campaign_pipeline.py
export const PIPELINE_NODES = [
  {
    step: 1,
    key: 'brand',
    agent: 'وكيل الهوية',
    icon: '🏷️',
    title: 'تحليل هوية البراند',
    doing: 'يقرأ ألوان علامتك ونبرة صوتها وكلماتها المفضّلة والممنوعة، ويبني دليل الهوية الذي يلتزم به بقية الوكلاء.',
    done: 'دليل الهوية جاهز',
  },
  {
    step: 2,
    key: 'strategy',
    agent: 'وكيل الاستراتيجية',
    icon: '📋',
    title: 'بناء استراتيجية الحملة',
    doing: 'يحدّد الهدف المحوري والجمهور وركائز المحتوى، ويوزّع المنتجات على أيام الحملة.',
    done: 'الاستراتيجية معتمدة',
  },
  {
    step: 3,
    key: 'products',
    agent: 'وكيل المنتجات',
    icon: '📦',
    title: 'تجهيز سياق المنتجات',
    doing: 'يجمع مواصفات كل منتج وصوره وسعره وفئته ليستند إليها النص والتصميم.',
    done: 'سياق المنتجات مُحمَّل',
  },
  {
    step: 4,
    key: 'ideas',
    agent: 'وكيل الأفكار',
    icon: '💡',
    title: 'توليد أفكار المنشورات',
    doing: 'يبتكر لكل يوم فكرة بزاوية إبداعية مختلفة، ويمنع تكرار صيغة الطرح بين المنشورات.',
    done: 'الأفكار جاهزة',
  },
  {
    step: 5,
    key: 'build',
    agent: 'لجنة المحتوى والتصميم',
    icon: '🧠',
    title: 'الكتابة والتقييم والتصميم',
    doing: 'لكل منشور: ثلاثة مرشحين نصيّين، ثم تقييم بنموذج Brand-DNA لاختيار الأقوى، ثم توليد صورة مربعة 1024×1024 بألوان علامتك.',
    done: 'المنشورات مكتوبة ومصمّمة',
  },
  {
    step: 6,
    key: 'assemble',
    agent: 'وكيل التجميع',
    icon: '🧩',
    title: 'تجميع كائن الحملة',
    doing: 'يربط النصوص بالصور والمنتجات والجدول الزمني في حملة واحدة متّسقة.',
    done: 'الحملة مكتملة',
  },
]

/** يستخرج رقم المرحلة الحالية من نص current_stage القادم من الخادم. */
export function stageToStep(stage) {
  const s = (stage || '').trim()
  if (!s) return 0
  if (s.includes('تهيئة') || s.includes('بانتظار')) return 0
  if (s.includes('هوية البراند')) return 1
  if (s.includes('استراتيجية')) return 2
  if (s.includes('سياق المنتجات')) return 3
  if (s.includes('أفكار')) return 4
  if (s.includes('المرشحين') || s.includes('توليد المنشور')) return 5
  if (s.includes('تجميع')) return 6
  if (s.includes('اكتملت')) return 7
  return 0
}

/** «توليد المنشور 2 من 3» → {cur: 2, total: 3} لعرض تقدّم فرعي. */
function subProgress(stage) {
  const m = (stage || '').match(/المنشور\s+(\d+)\s+من\s+(\d+)/)
  return m ? { cur: Number(m[1]), total: Number(m[2]) } : null
}

export default function CampaignPipeline({ stage, status, errorMessage, postsGenerated = 0 }) {
  const isFailed = status === 'failed'
  const isDone = status === 'done' || status === 'done_with_errors'
  const activeStep = isDone ? 7 : stageToStep(stage)
  const sub = subProgress(stage)

  // نسبة الإنجاز الكلية — تشمل التقدّم الفرعي داخل مرحلة البناء
  const pct = (() => {
    if (isDone) return 100
    if (activeStep <= 0) return 2
    let base = ((activeStep - 1) / PIPELINE_NODES.length) * 100
    if (sub && sub.total > 0) base += (sub.cur / sub.total) * (100 / PIPELINE_NODES.length)
    else base += 100 / PIPELINE_NODES.length / 2
    return Math.min(99, Math.round(base))
  })()

  const nodeState = (step) => {
    if (isDone) return 'done'
    if (isFailed) {
      if (step < activeStep) return 'done'
      if (step === activeStep) return 'failed'
      return 'pending'
    }
    if (step < activeStep) return 'done'
    if (step === activeStep) return 'active'
    return 'pending'
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* رأس البطاقة */}
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-bold text-gray-900 flex items-center gap-2">
          {isFailed ? (
            <><AlertTriangle size={17} className="text-red-600" /> تعطّل خط التوليد</>
          ) : isDone ? (
            <><Check size={17} className="text-emerald-600" /> اكتمل خط التوليد</>
          ) : (
            <><Loader size={17} className="text-primary-600 animate-spin" /> خط توليد الحملة يعمل الآن</>
          )}
        </h3>
        <span className={`text-sm font-bold ${isFailed ? 'text-red-600' : isDone ? 'text-emerald-600' : 'text-primary-600'}`}>
          {pct}%
        </span>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        {isFailed
          ? 'توقّف التنفيذ عند العقدة المُعلَّمة بالأحمر أدناه.'
          : isDone
            ? `مرّت الحملة بكل العقد الست بنجاح${postsGenerated ? ` — ${postsGenerated} منشور` : ''}.`
            : 'كل عقدة وكيل ذكاء اصطناعي مستقل يسلّم نتيجته للعقدة التالية.'}
      </p>

      {/* شريط التقدّم الكلي */}
      <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden mb-6">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${
            isFailed ? 'bg-red-500' : isDone ? 'bg-emerald-500' : 'bg-gradient-to-l from-primary-500 to-cyan-400'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* العُقد */}
      <ol className="relative">
        {PIPELINE_NODES.map((node, idx) => {
          const st = nodeState(node.step)
          const isLast = idx === PIPELINE_NODES.length - 1

          const ring =
            st === 'active' ? 'border-primary-500 bg-primary-50 shadow-[0_0_0_4px_rgba(59,130,246,0.12)]'
            : st === 'done' ? 'border-emerald-400 bg-emerald-50'
            : st === 'failed' ? 'border-red-400 bg-red-50'
            : 'border-gray-200 bg-gray-50'

          const connector =
            st === 'done' ? 'bg-emerald-300'
            : st === 'active' ? 'bg-gradient-to-b from-primary-400 to-gray-200'
            : 'bg-gray-200'

          return (
            <li key={node.key} className="relative flex gap-3 pb-5 last:pb-0">
              {/* الخط الواصل */}
              {!isLast && (
                <span
                  className={`absolute top-10 w-0.5 ${connector}`}
                  style={{ insetInlineStart: '1.187rem', bottom: '0.25rem' }}
                  aria-hidden
                />
              )}

              {/* دائرة العقدة */}
              <div
                className={`relative z-10 w-10 h-10 rounded-xl border-2 flex items-center justify-center flex-shrink-0 transition-all duration-500 ${ring}`}
              >
                {st === 'done' ? (
                  <Check size={17} className="text-emerald-600" />
                ) : st === 'failed' ? (
                  <AlertTriangle size={16} className="text-red-600" />
                ) : st === 'active' ? (
                  <span className="text-lg animate-pulse">{node.icon}</span>
                ) : (
                  <span className="text-base opacity-35 grayscale">{node.icon}</span>
                )}

                {/* نبضة حول العقدة العاملة */}
                {st === 'active' && (
                  <span className="absolute inset-0 rounded-xl border-2 border-primary-400 animate-ping opacity-40" aria-hidden />
                )}
              </div>

              {/* المحتوى */}
              <div className="flex-1 min-w-0 pt-0.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={`text-sm font-bold ${
                      st === 'pending' ? 'text-gray-400'
                      : st === 'failed' ? 'text-red-700'
                      : st === 'done' ? 'text-gray-700'
                      : 'text-primary-700'
                    }`}
                  >
                    {node.title}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium border ${
                      st === 'active' ? 'bg-primary-50 text-primary-700 border-primary-200'
                      : st === 'done' ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : st === 'failed' ? 'bg-red-50 text-red-700 border-red-200'
                      : 'bg-gray-50 text-gray-400 border-gray-200'
                    }`}
                  >
                    {node.agent}
                  </span>
                  {st === 'active' && sub && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-cyan-50 text-cyan-700 border border-cyan-200 font-bold">
                      {sub.cur} / {sub.total}
                    </span>
                  )}
                </div>

                {/* الشرح: يظهر كاملاً للعقدة العاملة، ومختصراً لغيرها */}
                {st === 'active' || st === 'failed' ? (
                  <p className={`text-xs mt-1 leading-6 ${st === 'failed' ? 'text-red-600' : 'text-gray-600'}`}>
                    {node.doing}
                  </p>
                ) : (
                  <p className={`text-xs mt-0.5 ${st === 'done' ? 'text-emerald-600' : 'text-gray-400'}`}>
                    {st === 'done' ? node.done : 'في الانتظار'}
                  </p>
                )}

                {/* شريط فرعي داخل مرحلة البناء */}
                {st === 'active' && sub && sub.total > 0 && (
                  <div className="w-full h-1 bg-gray-100 rounded-full overflow-hidden mt-2">
                    <div
                      className="h-full bg-cyan-400 rounded-full transition-all duration-500"
                      style={{ width: `${(sub.cur / sub.total) * 100}%` }}
                    />
                  </div>
                )}

                {/* رسالة الخطأ عند العقدة المتعطّلة */}
                {st === 'failed' && errorMessage && (
                  <p className="text-[11px] mt-2 p-2 rounded-lg bg-red-50 border border-red-200 text-red-700 leading-5 break-words">
                    {errorMessage}
                  </p>
                )}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
