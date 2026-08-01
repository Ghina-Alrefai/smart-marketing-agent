import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Sparkles, Image as ImageIcon, FileText } from 'lucide-react'
import clsx from 'clsx'
import useStore from '../store'
import { sendChatMessage } from '../api/client'

const EXAMPLES = [
  'صمّم صورة لمنتج HOCO',
  'اكتب منشور عن لابتوب ASUS',
  'اعمل خطة 7 أيام',
]

// ── عرض نتيجة التنفيذ بشكل جميل حسب نوعها ────────────────────────────────────
function ResultCard({ data }) {
  if (!data) return null
  const design = data.design || (data.image_url ? data : null)
  const imgUrl = design?.image_url
  const isImg = imgUrl && (imgUrl.startsWith('/uploads') || imgUrl.startsWith('http'))
  const hasPost = data.hook || data.caption || data.cta

  // خطة كاملة
  if (data.plan_id !== undefined) {
    return (
      <div className="mt-2 text-sm bg-primary-50 rounded-xl p-3 text-primary-800">
        📅 {data.message}
      </div>
    )
  }

  return (
    <div className="mt-2 space-y-3">
      {hasPost && (
        <div className="bg-gray-50 rounded-xl p-3 space-y-1.5 text-sm">
          <div className="flex items-center gap-1.5 text-gray-400 text-xs font-semibold">
            <FileText size={13} /> المنشور
          </div>
          {data.hook && <p className="font-bold text-gray-900">{data.hook}</p>}
          {data.caption && <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{data.caption}</p>}
          {data.cta && <p className="text-primary-600 font-semibold">👉 {data.cta}</p>}
          {Array.isArray(data.hashtags) && data.hashtags.length > 0 && (
            <p className="text-primary-500 text-xs">{data.hashtags.join('  ')}</p>
          )}
          {data.review && (
            <p className={clsx('text-xs mt-1', data.review.approved ? 'text-green-600' : 'text-amber-600')}>
              {data.review.approved ? '✓ اجتاز المراجعة' : '⚠ يحتاج تعديلاً'} — {data.review.notes || data.review.review_summary || ''}
            </p>
          )}
        </div>
      )}
      {design && (
        <div className="bg-gray-50 rounded-xl p-3 space-y-2 text-sm">
          <div className="flex items-center gap-1.5 text-gray-400 text-xs font-semibold">
            <ImageIcon size={13} /> التصميم
          </div>
          {isImg
            ? <img src={imgUrl} alt="التصميم" className="rounded-lg max-h-72 w-auto border border-gray-200" />
            : <p className="text-gray-500 text-xs">وصف الصورة: {design.image_prompt || imgUrl || '—'}</p>}
        </div>
      )}
      {!hasPost && !design && (
        <pre className="bg-gray-50 rounded-xl p-3 text-xs text-gray-600 overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

export default function ChatPage() {
  const { user, activeBrandId } = useStore()
  const userId = user?.id ?? 1
  const brandId = activeBrandId ?? 1

  const [messages, setMessages] = useState([
    { role: 'agent', text: 'مرحباً! 👋 أنا مساعدك التسويقي لفيسبوك. اطلب مني كتابة منشور، تصميم صورة، مراجعة نص، أو إنشاء خطة محتوى.' },
  ])
  const [input, setInput] = useState('')
  const [sessionId, setSessionId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [dryRun, setDryRun] = useState(false)
  const endRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  async function send(text) {
    const msg = (text ?? input).trim()
    if (!msg || loading) return
    setInput('')
    setMessages(m => [...m, { role: 'user', text: msg }])
    setLoading(true)
    try {
      const { data } = await sendChatMessage({
        user_id: userId, brand_id: brandId, message: msg,
        session_id: sessionId, dry_run: dryRun,
      })
      setSessionId(data.session_id)
      setMessages(m => [...m, {
        role: 'agent', text: data.message, type: data.type,
        options: data.options, data: data.data,
      }])
    } catch (e) {
      setMessages(m => [...m, { role: 'agent', text: '❌ تعذّر الاتصال بالخادم. تأكد أن الـ backend يعمل على المنفذ 8000.' }])
    } finally {
      setLoading(false)
    }
  }

  // نص القيمة المُرسَلة عند الضغط على خيار (منتج مثلاً)
  const optionMessage = (o) =>
    o.value?.product_id !== undefined ? `product_id:${o.value.product_id}` : (o.label || '')

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-4 border-b border-gray-100 bg-white flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-primary-600 rounded-xl flex items-center justify-center">
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <h1 className="font-bold text-gray-900">المساعد الذكي</h1>
            <p className="text-xs text-gray-400">فيسبوك · user #{userId} · brand #{brandId}</p>
          </div>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
          <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />
          وضع تجريبي (بلا توليد فعلي)
        </label>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 bg-gray-50">
        <div className="max-w-2xl mx-auto flex flex-col gap-4">
          {messages.map((m, i) => (
            <div key={i} className={clsx('flex gap-2.5 max-w-[85%]', m.role === 'user' ? 'self-start flex-row' : 'self-end flex-row-reverse')}>
              <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
                m.role === 'user' ? 'bg-primary-600 text-white' : 'bg-white border border-gray-200 text-primary-600')}>
                {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className={clsx('rounded-2xl px-4 py-2.5',
                m.role === 'user' ? 'bg-primary-600 text-white' : 'bg-white border border-gray-200 text-gray-800')}>
                <p className="whitespace-pre-wrap leading-relaxed text-sm">{m.text}</p>

                {/* أزرار الخيارات (اختيار منتج مثلاً) */}
                {m.options?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {m.options.map((o, j) => (
                      <button key={j} onClick={() => send(optionMessage(o))}
                        className="text-xs bg-primary-50 text-primary-700 hover:bg-primary-100 border border-primary-200 rounded-lg px-3 py-1.5 font-medium transition-colors">
                        {o.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* نتيجة التنفيذ */}
                {m.data && <ResultCard data={m.data} />}
              </div>
            </div>
          ))}

          {loading && (
            <div className="self-end flex gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-white border border-gray-200 text-primary-600 flex items-center justify-center">
                <Bot size={16} />
              </div>
              <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                <span className="inline-flex gap-1">
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-gray-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      {/* Composer */}
      <div className="border-t border-gray-100 bg-white px-4 md:px-8 py-4">
        <div className="max-w-2xl mx-auto">
          {messages.length <= 1 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {EXAMPLES.map((ex, i) => (
                <button key={i} onClick={() => send(ex)}
                  className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full px-3 py-1.5 transition-colors">
                  {ex}
                </button>
              ))}
            </div>
          )}
          <div className="flex items-end gap-2">
            <textarea
              className="input flex-1 resize-none"
              rows={1}
              placeholder="اكتب رسالتك..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            />
            <button onClick={() => send()} disabled={loading || !input.trim()}
              className="btn-primary flex items-center justify-center w-11 h-11 !p-0 flex-shrink-0 disabled:opacity-40">
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
