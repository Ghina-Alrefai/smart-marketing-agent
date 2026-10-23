import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertTriangle, CalendarClock, Check, ChevronDown, CircleDashed,
  Clock3, Fingerprint, Gauge, Layers3, Lightbulb, ListChecks, LockKeyhole,
  PackageSearch, Palette, PenTool, Route, Sparkles, Target, WifiOff, XCircle,
} from 'lucide-react'

/**
 * غرفة عمليات توليد الحملة.
 * المصدر الأساسي هو plan.pipeline_state القادم من الخادم. ويحتفظ المكوّن
 * بمسار fallback للحملات القديمة التي لا تملك إلا current_stage.
 */
export const PIPELINE_NODES = [
  { key: 'orchestrator', phase: 'planning', agent: 'Orchestrator Agent', title: 'تنسيق العملية', description: 'يتحقق من المدخلات ويوجه كل مخرج إلى الوكيل المناسب.', icon: Route },
  { key: 'brand', phase: 'planning', agent: 'Brand Agent', title: 'فهم هوية البراند', description: 'يستدعي Brand DNA والنبرة والألوان والقواعد الثابتة.', icon: Fingerprint },
  { key: 'strategy', phase: 'planning', agent: 'Strategy Agent', title: 'بناء الاستراتيجية', description: 'يحدد الهدف والجمهور والرسالة وركائز المحتوى.', icon: Target },
  { key: 'products', phase: 'planning', agent: 'Product Agent', title: 'تحضير المنتجات', description: 'يجمع المواصفات والصور والأسعار ليمنع اختلاق المعلومات.', icon: PackageSearch },
  { key: 'ideas', phase: 'planning', agent: 'Idea Agent', title: 'ابتكار الأفكار', description: 'يصنع زاوية ورسالة واتجاهاً بصرياً مختلفاً لكل منشور.', icon: Lightbulb },
  { key: 'copywriter', phase: 'production', agent: 'Copywriter Agent', title: 'كتابة المرشحين', description: 'ينتج ثلاثة نصوص بديلة لكل فكرة مع تطبيق نبرة البراند.', icon: PenTool },
  { key: 'evaluator', phase: 'production', agent: 'Brand DNA Evaluator', title: 'ترتيب المرشحين', description: 'يفحص القيود ويرتب البدائل ويختار المرشح الأقوى.', icon: Gauge },
  { key: 'designer', phase: 'production', agent: 'Designer Agent', title: 'إنشاء التصميم', description: 'يحوّل الفكرة المختارة إلى صورة هادئة ومتسقة مع الهوية.', icon: Palette },
  { key: 'quality', phase: 'production', agent: 'Quality Agent', title: 'فحص النتيجة', description: 'يتحقق من اتساق النص والصورة ويجهز المنشور للمراجعة.', icon: ListChecks },
  { key: 'assembler', phase: 'delivery', agent: 'Campaign Assembler', title: 'تجميع الحملة', description: 'يربط الاستراتيجية والمنشورات والتصاميم في نتيجة واحدة.', icon: Layers3 },
  { key: 'scheduler', phase: 'delivery', agent: 'Scheduler Agent', title: 'الجدولة والنشر', description: 'ينتظر اعتمادك؛ لن يجدول أو ينشر أي منشور من تلقاء نفسه.', icon: CalendarClock },
]

const PHASES = [
  { key: 'planning', number: '01', title: 'الفهم والتخطيط', description: 'تحويل طلبك وبيانات البراند إلى خطة قابلة للتنفيذ' },
  { key: 'production', number: '02', title: 'حلقة إنتاج المنشورات', description: 'تتكرر لكل منشور: كتابة ← تقييم ← تصميم ← جودة' },
  { key: 'delivery', number: '03', title: 'التجميع والتسليم', description: 'حفظ الحملة ثم انتظار قرارك قبل الجدولة' },
]

const STATE_VIEW = {
  pending: { label: 'في الانتظار', icon: CircleDashed, tone: 'pending' },
  queued: { label: 'في الطابور', icon: Clock3, tone: 'pending' },
  waiting: { label: 'بانتظار المنشور التالي', icon: Clock3, tone: 'waiting' },
  active: { label: 'يعمل الآن', icon: Activity, tone: 'active' },
  completed: { label: 'مكتمل', icon: Check, tone: 'completed' },
  warning: { label: 'اكتمل جزئياً', icon: AlertTriangle, tone: 'warning' },
  failed: { label: 'توقّف هنا', icon: XCircle, tone: 'failed' },
  waiting_approval: { label: 'بانتظار اعتمادك', icon: LockKeyhole, tone: 'approval' },
}

function legacyStageKey(stage = '') {
  if (stage.includes('هوية البراند')) return 'brand'
  if (stage.includes('استراتيجية')) return 'strategy'
  if (stage.includes('سياق المنتجات')) return 'products'
  if (stage.includes('أفكار')) return 'ideas'
  if (stage.includes('المرشحين') || stage.includes('توليد المنشور')) return 'copywriter'
  if (stage.includes('تجميع')) return 'assembler'
  if (stage.includes('اكتملت')) return 'scheduler'
  return 'orchestrator'
}

/** توافق خلفي مع أي كود قديم كان يعتمد رقم المرحلة. */
export function stageToStep(stage) {
  const key = legacyStageKey(stage || '')
  return PIPELINE_NODES.findIndex(node => node.key === key) + 1
}

function legacyState(stage, status, postsGenerated) {
  const activeKey = legacyStageKey(stage || '')
  const activeIndex = PIPELINE_NODES.findIndex(node => node.key === activeKey)
  const finished = status === 'done' || status === 'done_with_errors'
  const failed = status === 'failed'
  const nodes = PIPELINE_NODES.map((definition, index) => {
    let nodeStatus = 'pending'
    if (finished) nodeStatus = definition.key === 'scheduler' ? 'waiting_approval' : 'completed'
    else if (index < activeIndex) nodeStatus = 'completed'
    else if (index === activeIndex) nodeStatus = failed ? 'failed' : 'active'
    return { key: definition.key, status: nodeStatus, activity: index === activeIndex ? stage : undefined, completed_items: 0, failed_items: 0, total_items: 0 }
  })
  return {
    status: finished ? status : failed ? 'failed' : 'running',
    active_node: finished ? null : activeKey,
    overall_progress: finished ? 100 : Math.max(2, Math.round((activeIndex / (PIPELINE_NODES.length - 2)) * 100)),
    posts_generated: postsGenerated,
    total_posts: 0,
    current_post: null,
    nodes,
    events: stage ? [{ sequence: 1, node_key: activeKey, status: failed ? 'failed' : 'active', message: stage }] : [],
  }
}

function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return '—'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds} ث`
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes < 60) return `${minutes} د ${rest} ث`
  return `${Math.floor(minutes / 60)} س ${minutes % 60} د`
}

function eventTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function stateClasses(status) {
  const tone = (STATE_VIEW[status] || STATE_VIEW.pending).tone
  return {
    active: 'border-indigo-400 bg-indigo-50/80 shadow-[0_12px_35px_-22px_rgba(79,70,229,.9)] pipeline-node-active',
    completed: 'border-emerald-200 bg-emerald-50/55',
    warning: 'border-amber-300 bg-amber-50/70',
    failed: 'border-red-300 bg-red-50/80',
    approval: 'border-violet-300 bg-violet-50/70',
    waiting: 'border-slate-200 bg-white',
    pending: 'border-slate-200 bg-slate-50/60',
  }[tone]
}

function NodeCard({ node, definition, isCurrent }) {
  const Icon = definition.icon
  const view = STATE_VIEW[node.status] || STATE_VIEW.pending
  const StateIcon = view.icon
  const hasItems = Number(node.total_items) > 0
  const completedItems = Number(node.completed_items || 0)
  const failedItems = Number(node.failed_items || 0)

  return (
    <article className={`pipeline-node relative min-w-[178px] flex-1 rounded-2xl border p-3.5 transition-all duration-500 ${stateClasses(node.status)}`} aria-current={isCurrent ? 'step' : undefined}>
      {isCurrent && <span className="pipeline-node-scan" aria-hidden />}
      <div className="relative z-10 flex items-start justify-between gap-2">
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl border ${
          node.status === 'active' ? 'border-indigo-200 bg-white text-indigo-600'
            : node.status === 'completed' ? 'border-emerald-200 bg-white text-emerald-600'
              : node.status === 'failed' ? 'border-red-200 bg-white text-red-600'
                : node.status === 'waiting_approval' ? 'border-violet-200 bg-white text-violet-600'
                  : 'border-slate-200 bg-white text-slate-400'
        }`}><Icon size={18} strokeWidth={1.9} /></div>
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[9px] font-bold ${
          node.status === 'active' ? 'bg-indigo-600 text-white'
            : node.status === 'completed' ? 'bg-emerald-100 text-emerald-700'
              : node.status === 'failed' ? 'bg-red-100 text-red-700'
                : node.status === 'warning' ? 'bg-amber-100 text-amber-700'
                  : node.status === 'waiting_approval' ? 'bg-violet-100 text-violet-700'
                    : 'bg-slate-100 text-slate-500'
        }`}><StateIcon size={10} className={node.status === 'active' ? 'animate-pulse' : ''} />{view.label}</span>
      </div>

      <div className="relative z-10 mt-3">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400" dir="ltr">{definition.agent}</p>
        <h4 className={`mt-1 text-sm font-extrabold ${node.status === 'pending' ? 'text-slate-500' : 'text-slate-900'}`}>{definition.title}</h4>
        <p className={`mt-1.5 min-h-[38px] text-[11px] leading-[1.65] ${node.status === 'active' ? 'text-indigo-800' : node.status === 'failed' ? 'text-red-700' : 'text-slate-500'}`}>
          {node.status === 'pending' ? definition.description : (node.activity || node.output_summary || definition.description)}
        </p>
        {hasItems && (
          <div className="mt-3">
            <div className="mb-1.5 flex items-center justify-between text-[10px] font-bold text-slate-500">
              <span>{completedItems} / {node.total_items} منشور</span>
              {failedItems > 0 && <span className="text-amber-700">{failedItems} تعذّر</span>}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-slate-200/80">
              <div className={`h-full rounded-full transition-all duration-700 ${failedItems ? 'bg-amber-400' : 'bg-indigo-500'}`} style={{ width: `${Math.min(100, (completedItems / node.total_items) * 100)}%` }} />
            </div>
          </div>
        )}
      </div>
    </article>
  )
}

function Connector({ from, to }) {
  const complete = from.status === 'completed'
  const active = from.status === 'active' || to.status === 'active'
  const failed = from.status === 'failed'
  return <div className="pipeline-connector-wrap flex min-w-[34px] items-center justify-center" aria-hidden><span className={`pipeline-connector ${complete ? 'is-complete' : ''} ${active ? 'is-active' : ''} ${failed ? 'is-failed' : ''}`} /></div>
}

export default function CampaignPipeline({ pipeline, stage, status, errorMessage, postsGenerated = 0 }) {
  const [showAllEvents, setShowAllEvents] = useState(false)
  const state = useMemo(() => pipeline?.nodes?.length ? pipeline : legacyState(stage, status, postsGenerated), [pipeline, stage, status, postsGenerated])
  const isDemo = Boolean(state.is_demo || state.execution_mode === 'offline_demo')
  const nodes = useMemo(() => {
    const byKey = new Map((state.nodes || []).map(node => [node.key, node]))
    return PIPELINE_NODES.map(definition => ({ ...definition, ...(byKey.get(definition.key) || { status: 'pending', activity: 'في الانتظار' }) }))
  }, [state.nodes])

  const running = ['queued', 'running', 'generating'].includes(state.status)
  const failed = state.status === 'failed' || status === 'failed'
  const partial = state.status === 'done_with_errors' || status === 'done_with_errors'
  const finished = state.status === 'done' || status === 'done'
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!running) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [running])

  const activeNode = nodes.find(node => node.key === state.active_node)
    || nodes.find(node => node.status === 'failed')
    || nodes.find(node => node.status === 'waiting_approval')
    || nodes[0]
  const ActiveIcon = activeNode.icon
  const progress = Math.max(0, Math.min(100, Number(state.overall_progress || 0)))
  const startedAt = state.started_at ? new Date(state.started_at).getTime() : null
  const completedAt = state.completed_at ? new Date(state.completed_at).getTime() : null
  const elapsed = startedAt ? (completedAt || now) - startedAt : null
  const events = [...(state.events || [])].reverse()
  const visibleEvents = showAllEvents ? events : events.slice(0, 6)
  const totalPosts = Number(state.total_posts || 0)
  const createdPosts = Math.max(Number(state.posts_generated || 0), postsGenerated)
  const currentPost = state.current_post
  const header = failed
    ? { title: 'توقّف خط التنفيذ', subtitle: 'حددنا العقدة التي فشلت وحفظنا سبب الخطأ لتتمكن من إعادة المحاولة.' }
    : isDemo && finished
      ? { title: 'نتائج العرض جاهزة لمراجعتك', subtitle: 'اكتمل التسلسل التوضيحي وحُمّلت النتائج المحضّرة مسبقاً دون أي استدعاء لنموذج خارجي.' }
      : partial
      ? { title: 'اكتملت الحملة جزئياً', subtitle: 'حُفظت النتائج الناجحة، ويمكنك مراجعتها قبل اتخاذ القرار.' }
      : finished
        ? { title: 'الحملة جاهزة لمراجعتك', subtitle: 'أنهى الوكلاء عملهم. الجدولة ما زالت مقفلة حتى تعتمد المنشورات.' }
        : { title: 'غرفة عمليات الحملة تعمل الآن', subtitle: 'تشاهد انتقال العمل الفعلي بين الوكلاء لحظة بلحظة.' }

  return (
    <section className="campaign-pipeline-shell overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-[0_24px_70px_-42px_rgba(15,23,42,.45)]">
      <div className="border-b border-slate-200 bg-[radial-gradient(circle_at_top_right,rgba(99,102,241,.12),transparent_38%),linear-gradient(135deg,#fff,#f8fafc)] p-5 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-extrabold ${failed ? 'bg-red-100 text-red-700' : isDemo ? 'bg-cyan-100 text-cyan-800' : finished ? 'bg-emerald-100 text-emerald-700' : partial ? 'bg-amber-100 text-amber-700' : 'bg-indigo-100 text-indigo-700'}`}>
                {running && <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 pipeline-live-dot" />}
                {failed ? 'يحتاج تدخلاً' : finished || partial ? 'جاهز للمراجعة' : 'تنفيذ حي'}
              </span>
              <span className="text-[11px] font-semibold text-slate-400">Campaign Pipeline · Live Trace</span>
            </div>
            <h3 className="text-xl font-black tracking-tight text-slate-950 sm:text-2xl">{header.title}</h3>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">{header.subtitle}</p>
          </div>
          <div className="flex items-center gap-4 rounded-2xl border border-white/80 bg-white/80 px-4 py-3 shadow-sm backdrop-blur">
            <div className="relative flex h-16 w-16 items-center justify-center rounded-full" style={{ background: `conic-gradient(${failed ? '#ef4444' : partial ? '#f59e0b' : '#4f46e5'} ${progress * 3.6}deg, #e2e8f0 0deg)` }}>
              <div className="flex h-[52px] w-[52px] items-center justify-center rounded-full bg-white text-sm font-black text-slate-900">{progress}%</div>
            </div>
            <div className="min-w-[120px]">
              <p className="text-[10px] font-bold text-slate-400">التقدم الكلي</p>
              <p className="mt-0.5 text-sm font-extrabold text-slate-800">{createdPosts}{totalPosts ? ` من ${totalPosts}` : ''} منشور</p>
              <p className="mt-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500"><Clock3 size={12} /> {formatDuration(elapsed)}</p>
            </div>
          </div>
        </div>
        
        <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-200/70"><div className={`pipeline-master-progress h-full rounded-full transition-all duration-700 ${failed ? 'bg-red-500' : partial ? 'bg-amber-500' : 'bg-gradient-to-l from-indigo-600 via-violet-500 to-cyan-400'}`} style={{ width: `${progress}%` }} /></div>
      </div>

      <div className="grid gap-5 p-5 sm:p-6 xl:grid-cols-[minmax(0,1fr)_310px]">
        <div className="min-w-0 space-y-5">
          <div className={`pipeline-focus relative overflow-hidden rounded-3xl p-5 text-white ${failed ? 'bg-gradient-to-br from-red-950 via-red-900 to-slate-950' : 'bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900'}`}>
            <div className="pipeline-focus-grid" aria-hidden />
            <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center">
              <div className="relative flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-white/10">
                <ActiveIcon size={25} />
                {running && <span className="absolute -inset-1 rounded-[20px] border border-cyan-300/40 pipeline-focus-ring" aria-hidden />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-[.16em] text-cyan-300" dir="ltr">{activeNode.agent}</span>
                  {currentPost?.total > 0 && running && <span className="rounded-full border border-white/15 bg-white/10 px-2 py-0.5 text-[10px] font-bold text-white/80">المنشور {currentPost.index} من {currentPost.total}</span>}
                </div>
                <div className="mt-1 flex items-center gap-2"><h4 className="text-lg font-black">{activeNode.title}</h4>{running && <Activity size={16} className="animate-pulse text-cyan-300" />}</div>
                <p className="mt-1.5 text-sm leading-6 text-slate-300">{activeNode.activity || activeNode.output_summary || activeNode.description}</p>
                {failed && (state.error || errorMessage) && <p className="mt-3 rounded-xl border border-red-300/20 bg-red-500/10 px-3 py-2 text-xs leading-5 text-red-100">{state.error || errorMessage}</p>}
              </div>
            </div>
            {running && <div className="relative z-10 mt-4 flex items-center gap-2 border-t border-white/10 pt-3 text-[11px] text-slate-400"><Sparkles size={13} className="text-cyan-300" />{isDemo ? 'تُعرض مراحل النظام حتمياً، ثم تُحمّل بيانات العرض المحضّرة للمراجعة البشرية.' : 'يمكنك مغادرة الصفحة؛ سيستمر التنفيذ وستعود إلى الحالة نفسها عند فتح الحملة مجدداً.'}</div>}
          </div>

          {PHASES.map(phase => {
            const phaseNodes = nodes.filter(node => node.phase === phase.key)
            return (
              <section key={phase.key} className="rounded-3xl border border-slate-200 bg-slate-50/55 p-4">
                <div className="mb-3 flex items-start gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-900 text-[10px] font-black text-white">{phase.number}</span>
                  <div><h4 className="text-sm font-black text-slate-900">{phase.title}</h4><p className="mt-0.5 text-[11px] leading-5 text-slate-500">{phase.description}</p></div>
                  {phase.key === 'production' && totalPosts > 0 && <span className="mr-auto rounded-full bg-indigo-100 px-2.5 py-1 text-[10px] font-extrabold text-indigo-700">× {totalPosts} منشور</span>}
                </div>
                <div className="pipeline-lane overflow-x-auto pb-1">
                  <div className="flex min-w-max items-stretch lg:min-w-0">
                    {phaseNodes.map((node, index) => (
                      <Fragment key={node.key}>
                        <NodeCard node={node} definition={node} isCurrent={node.key === activeNode.key && (running || failed)} />
                        {index < phaseNodes.length - 1 && <Connector from={node} to={phaseNodes[index + 1]} />}
                      </Fragment>
                    ))}
                  </div>
                </div>
              </section>
            )
          })}
        </div>

        <aside className="min-w-0">
          <div className="sticky top-5 rounded-3xl border border-slate-200 bg-slate-950 p-4 text-white shadow-[0_22px_55px_-35px_rgba(15,23,42,.9)]">
            <div className="flex items-center justify-between gap-3">
              <div><p className="text-[10px] font-bold uppercase tracking-[.15em] text-cyan-300" dir="ltr">{'Live activity'}</p><h4 className="mt-1 text-sm font-black">سجل انتقال العمل</h4></div>
              <span className="rounded-full bg-white/10 px-2 py-1 text-[10px] font-bold text-slate-300">{state.event_count || events.length} حدث</span>
            </div>
            <div className="mt-4 space-y-0">
              {visibleEvents.length === 0 ? <div className="rounded-2xl border border-dashed border-white/15 p-4 text-center text-xs text-slate-400">سيظهر انتقال العمل هنا عند بدء أول وكيل.</div> : visibleEvents.map((event, index) => {
                const definition = PIPELINE_NODES.find(node => node.key === event.node_key) || PIPELINE_NODES[0]
                const EventIcon = definition.icon
                const eventTone = event.status === 'failed' ? 'bg-red-400' : event.status === 'warning' ? 'bg-amber-400' : event.status === 'completed' ? 'bg-emerald-400' : event.status === 'waiting_approval' ? 'bg-violet-400' : 'bg-cyan-400'
                return (
                  <div key={`${event.sequence || index}-${event.at || index}`} className="relative flex gap-3 pb-4 last:pb-0">
                    {index < visibleEvents.length - 1 && <span className="absolute right-[13px] top-7 bottom-0 w-px bg-white/10" aria-hidden />}
                    <span className={`relative z-10 mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg ${eventTone} text-slate-950`}><EventIcon size={13} /></span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2"><p className="truncate text-[10px] font-bold text-slate-300">{definition.title}</p><time className="flex-shrink-0 text-[9px] text-slate-500">{eventTime(event.at)}</time></div>
                      <p className="mt-0.5 text-[11px] leading-5 text-slate-100">{event.message}</p>
                      {event.post_index && <span className="mt-1 inline-flex rounded-md bg-white/5 px-1.5 py-0.5 text-[9px] text-slate-400">منشور {event.post_index}/{event.total_posts || totalPosts}{event.duration_ms != null ? ` · ${formatDuration(event.duration_ms)}` : ''}</span>}
                      {event.detail && ['failed', 'warning'].includes(event.status) && <p className="mt-1 text-[10px] leading-4 text-red-300">{event.detail}</p>}
                    </div>
                  </div>
                )
              })}
            </div>
            {events.length > 6 && <button type="button" onClick={() => setShowAllEvents(value => !value)} className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-[11px] font-bold text-slate-300 transition-colors hover:bg-white/10">{showAllEvents ? 'عرض آخر 6 أحداث' : `عرض السجل الكامل (${events.length})`}<ChevronDown size={13} className={`transition-transform ${showAllEvents ? 'rotate-180' : ''}`} /></button>}
            <div className="mt-4 grid grid-cols-2 gap-2 border-t border-white/10 pt-4">
              <div className="rounded-xl bg-white/5 p-2.5"><p className="text-[9px] text-slate-500">منشورات محفوظة</p><p className="mt-1 text-lg font-black text-white">{createdPosts}</p></div>
              <div className="rounded-xl bg-white/5 p-2.5"><p className="text-[9px] text-slate-500">زمن التنفيذ</p><p className="mt-1 text-sm font-black text-white">{formatDuration(elapsed)}</p></div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}
