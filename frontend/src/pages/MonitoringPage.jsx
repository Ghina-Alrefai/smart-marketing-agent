import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, DollarSign, Zap, Clock, CheckCircle2, AlertTriangle,
  RotateCcw, Megaphone, ChevronDown,
} from 'lucide-react'
import useStore from '../store'
import {
  getMonitoringOverview, getMonitoringAgents, getMonitoringCampaigns, getMonitoringErrors,
} from '../api/client'

// ── لوحة ألوان متسقة مع هوية النظام (indigo-600 هو Slot 1) ──────────────────
// الترتيب ثابت (لا يُعاد تدويره) — يحافظ على أقصى تباين بين الفئات المتجاورة.
const SERIES = ['#4f46e5', '#0ea5a3', '#eda100', '#16a34a', '#7c3aed', '#e34948', '#db2777', '#ea580c']
const AGENT_LABELS_AR = {
  brand_agent: 'وكيل البراند', strategy_agent: 'وكيل الاستراتيجية', product_agent: 'وكيل المنتجات',
  idea_agent: 'وكيل الأفكار', content_agent: 'وكيل المحتوى', design_agent: 'وكيل التصميم',
  review_agent: 'وكيل المراجعة', orchestrator_agent: 'المساعد التسويقي',
}
const agentLabel = (name) => AGENT_LABELS_AR[name] || name

const PERIODS = [
  { value: 'today', label: 'اليوم' },
  { value: '7d', label: '7 أيام' },
  { value: '30d', label: '30 يوماً' },
  { value: '90d', label: '90 يوماً' },
  { value: 'all', label: 'الكل' },
]

const fmtUSD = (n) => `$${Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`
const fmtCompact = (n) => {
  n = Number(n || 0)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return `${Math.round(n)}`
}
const fmtDuration = (ms) => {
  ms = Number(ms || 0)
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)} د`
  return `${(ms / 1000).toFixed(1)} ث`
}
const fmtDay = (iso) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('ar', { day: 'numeric', month: 'short' })
}

// ── Stat tile ─────────────────────────────────────────────────────────────
function StatTile({ label, value, icon: Icon, tint, sub }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-gray-500 text-sm">{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1.5">{value}</p>
          {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
        </div>
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${tint}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  )
}

// ── مخطط خطي بسيط للاتجاه الزمني (تكلفة + طلبات) — SVG مضمّن، تلميحات hover ──
function TrendChart({ data }) {
  const [hover, setHover] = useState(null)
  const W = 720, H = 220, PAD_L = 44, PAD_R = 12, PAD_T = 16, PAD_B = 28
  const innerW = W - PAD_L - PAD_R
  const innerH = H - PAD_T - PAD_B

  if (!data?.length) {
    return <div className="h-56 flex items-center justify-center text-gray-400 text-sm">لا توجد بيانات لهذه الفترة</div>
  }

  const maxCost = Math.max(...data.map((d) => d.cost), 0.0001)
  const x = (i) => PAD_L + (i / Math.max(data.length - 1, 1)) * innerW
  const y = (v) => PAD_T + innerH - (v / maxCost) * innerH

  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(d.cost)}`).join(' ')
  const areaPath = `${linePath} L ${x(data.length - 1)} ${PAD_T + innerH} L ${x(0)} ${PAD_T + innerH} Z`

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * maxCost)

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-56" preserveAspectRatio="xMidYMid meet">
        {yTicks.map((t, i) => (
          <g key={i}>
            <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)} stroke="#e5e7eb" strokeWidth="1" />
            <text x={PAD_L - 8} y={y(t)} fontSize="10" fill="#9ca3af" textAnchor="end" dominantBaseline="middle">
              {t === 0 ? '$0' : `$${t.toFixed(3)}`}
            </text>
          </g>
        ))}
        <path d={areaPath} fill={SERIES[0]} opacity="0.08" />
        <path d={linePath} fill="none" stroke={SERIES[0]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => (
          <g key={d.day}>
            <circle
              cx={x(i)} cy={y(d.cost)} r={hover === i ? 5 : 3.5}
              fill={SERIES[0]} stroke="#fff" strokeWidth="2"
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
              style={{ cursor: 'pointer' }}
            />
            <rect x={x(i) - 10} y={PAD_T} width="20" height={innerH} fill="transparent"
                  onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
          </g>
        ))}
        {data.length <= 20 && data.map((d, i) => (
          i % Math.ceil(data.length / 8 || 1) === 0 && (
            <text key={d.day} x={x(i)} y={H - 8} fontSize="10" fill="#9ca3af" textAnchor="middle">
              {fmtDay(d.day)}
            </text>
          )
        ))}
      </svg>
      {hover !== null && data[hover] && (
        <div
          className="absolute pointer-events-none bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg -translate-x-1/2 -translate-y-full"
          style={{ left: `${(x(hover) / W) * 100}%`, top: `${(y(data[hover].cost) / H) * 100}%` }}
        >
          <p className="font-semibold">{fmtDay(data[hover].day)}</p>
          <p>التكلفة: {fmtUSD(data[hover].cost)}</p>
          <p>الطلبات: {data[hover].requests}</p>
          <p>Tokens: {fmtCompact(data[hover].tokens)}</p>
        </div>
      )}
    </div>
  )
}

// ── مخطط أعمدة أفقي لاستهلاك الوكلاء (Bar chart) ──────────────────────────
function AgentsBarChart({ agents }) {
  const [hover, setHover] = useState(null)
  if (!agents?.length) {
    return <div className="h-40 flex items-center justify-center text-gray-400 text-sm">لا توجد بيانات</div>
  }
  const maxCost = Math.max(...agents.map((a) => a.cost), 0.0001)

  return (
    <div className="space-y-3">
      {agents.map((a, i) => {
        const pct = Math.max((a.cost / maxCost) * 100, 2)
        const color = SERIES[i % SERIES.length]
        return (
          <div key={a.agent_name} className="group relative"
               onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <div className="flex items-center justify-between text-sm mb-1">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                <span className="font-medium text-gray-700">{agentLabel(a.agent_name)}</span>
              </div>
              <span className="font-semibold text-gray-900 tabular-nums">{fmtUSD(a.cost)}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            {hover === i && (
              <div className="absolute z-10 top-full mt-1 right-0 bg-gray-900 text-white text-xs rounded-lg px-3 py-2 shadow-lg whitespace-nowrap">
                <p>الطلبات: {a.requests} · Tokens: {fmtCompact(a.tokens)}</p>
                <p>متوسط الزمن: {fmtDuration(a.avg_duration_ms)} · فاشل: {a.failed}</p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── جدول الحملات ───────────────────────────────────────────────────────────
function CampaignsTable({ campaigns }) {
  if (!campaigns?.length) {
    return <div className="h-32 flex items-center justify-center text-gray-400 text-sm">لا توجد حملات في هذه الفترة</div>
  }
  return (
    <div className="overflow-x-auto -mx-2">
      <table className="w-full text-sm min-w-[560px]">
        <thead>
          <tr className="text-gray-400 text-right border-b border-gray-100">
            <th className="font-medium px-2 py-2">الحملة</th>
            <th className="font-medium px-2 py-2">الطلبات</th>
            <th className="font-medium px-2 py-2">Tokens</th>
            <th className="font-medium px-2 py-2">الزمن</th>
            <th className="font-medium px-2 py-2">التكلفة</th>
            <th className="font-medium px-2 py-2">الحالة</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((c) => (
            <tr key={c.content_plan_id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/60">
              <td className="px-2 py-2.5 font-medium text-gray-800">{c.campaign_name}</td>
              <td className="px-2 py-2.5 text-gray-600 tabular-nums">{c.requests}</td>
              <td className="px-2 py-2.5 text-gray-600 tabular-nums">{fmtCompact(c.tokens)}</td>
              <td className="px-2 py-2.5 text-gray-600 tabular-nums">{fmtDuration(c.duration_ms)}</td>
              <td className="px-2 py-2.5 font-semibold text-gray-900 tabular-nums">{fmtUSD(c.cost)}</td>
              <td className="px-2 py-2.5">
                {c.failed > 0 ? (
                  <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 rounded-full px-2 py-0.5 text-xs font-medium">
                    <AlertTriangle size={11} /> {c.failed} فشل
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 rounded-full px-2 py-0.5 text-xs font-medium">
                    <CheckCircle2 size={11} /> سليمة
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ErrorsList({ errors }) {
  if (!errors?.length) {
    return (
      <div className="h-24 flex flex-col items-center justify-center text-gray-400 text-sm gap-2">
        <CheckCircle2 size={22} className="text-emerald-400" />
        لا توجد أخطاء مسجّلة في هذه الفترة
      </div>
    )
  }
  return (
    <div className="space-y-2 max-h-72 overflow-y-auto">
      {errors.map((e) => (
        <div key={e.id} className="flex items-center justify-between text-sm bg-red-50/60 border border-red-100 rounded-xl px-3 py-2">
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle size={14} className="text-red-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="font-medium text-gray-800 truncate">{agentLabel(e.agent_name)} — {e.error_type}</p>
              <p className="text-xs text-gray-400" dir="ltr">{e.trace_id.slice(0, 18)}…</p>
            </div>
          </div>
          <div className="text-left flex-shrink-0">
            {e.retry_count > 0 && (
              <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                <RotateCcw size={11} /> {e.retry_count}
              </span>
            )}
            <p className="text-xs text-gray-400">{new Date(e.created_at).toLocaleString('ar', { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' })}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── الصفحة الرئيسية ─────────────────────────────────────────────────────────
export default function MonitoringPage() {
  const { user } = useStore()
  const isAdmin = user?.role === 'super_admin'
  const [period, setPeriod] = useState('30d')

  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ['monitoring', 'overview', period],
    queryFn: () => getMonitoringOverview(period).then((r) => r.data),
  })
  const { data: agents } = useQuery({
    queryKey: ['monitoring', 'agents', period],
    queryFn: () => getMonitoringAgents(period).then((r) => r.data),
  })
  const { data: campaigns } = useQuery({
    queryKey: ['monitoring', 'campaigns', period],
    queryFn: () => getMonitoringCampaigns(period, 8).then((r) => r.data),
  })
  const { data: errors } = useQuery({
    queryKey: ['monitoring', 'errors', period],
    queryFn: () => getMonitoringErrors(period, 6).then((r) => r.data),
  })

  const topAgents = useMemo(() => (agents || []).slice(0, 8), [agents])

  return (
    <div className="p-8" dir="rtl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8 flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity size={22} className="text-primary-600" />
            استهلاك الموارد والتكلفة
          </h1>
          <p className="text-gray-500 mt-1 text-sm">
            {isAdmin
              ? 'مراقبة تنفيذ الوكلاء واستهلاك نماذج الذكاء الاصطناعي على مستوى كل النظام'
              : 'ملخّص استهلاكك واستدعاءات الوكلاء ضمن حملاتك الخاصة'}
          </p>
        </div>

        {/* Period selector */}
        <div className="relative">
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="input pl-9 appearance-none bg-white cursor-pointer font-medium text-gray-700 w-40"
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <ChevronDown size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {loadingOverview ? (
        <div className="text-gray-400 text-sm">جارِ التحميل...</div>
      ) : (
        <>
          {/* Stat tiles */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
            <StatTile label="إجمالي التكلفة التقديرية" value={fmtUSD(overview?.total_cost)}
                      icon={DollarSign} tint="text-primary-600 bg-primary-50" />
            <StatTile label="إجمالي Tokens" value={fmtCompact(overview?.total_tokens)}
                      icon={Zap} tint="text-amber-600 bg-amber-50"
                      sub={`${overview?.total_requests ?? 0} طلب نموذج`} />
            <StatTile label="معدل نجاح العمليات" value={`${overview?.success_rate ?? 100}%`}
                      icon={CheckCircle2} tint="text-emerald-600 bg-emerald-50"
                      sub={`${overview?.failed_requests ?? 0} فاشلة`} />
            <StatTile label="متوسط زمن الحملة" value={fmtDuration(overview?.avg_campaign_duration_ms)}
                      icon={Clock} tint="text-violet-600 bg-violet-50"
                      sub={`${overview?.campaigns_count ?? 0} حملة`} />
          </div>

          {/* Trend + Agents */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="card lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-900">اتجاه التكلفة اليومي</h2>
                <span className="text-xs text-gray-400">التكلفة التقديرية بالدولار</span>
              </div>
              <TrendChart data={overview?.daily_trend} />
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-900">الأكثر استهلاكاً</h2>
                <Megaphone size={16} className="text-gray-300" />
              </div>
              <AgentsBarChart agents={topAgents} />
            </div>
          </div>

          {/* Campaigns + Errors */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="card lg:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-900">
                  {isAdmin ? 'أعلى الحملات تكلفةً' : 'حملاتك'}
                </h2>
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <RotateCcw size={12} /> {overview?.retry_count ?? 0} إعادة محاولة
                </span>
              </div>
              <CampaignsTable campaigns={campaigns} />
            </div>

            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-gray-900">أحدث الأخطاء</h2>
                <AlertTriangle size={16} className="text-gray-300" />
              </div>
              <ErrorsList errors={errors} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
