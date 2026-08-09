import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CalendarClock, Trash2, Clock, ImageIcon, Pencil, Check, X } from 'lucide-react'
import useStore from '../store'
import { listScheduled, deleteScheduled, updateScheduledTime } from '../api/client'
import ImageLightbox from '../components/ImageLightbox'

function formatWhen(sp) {
  if (sp.scheduled_at) {
    try {
      const d = new Date(sp.scheduled_at)
      return d.toLocaleString('ar', { dateStyle: 'medium', timeStyle: 'short' })
    } catch { /* noop */ }
  }
  return sp.time_text || 'وقت غير محدد'
}

// ISO → قيمة datetime-local ("YYYY-MM-DDTHH:MM")
function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d)) return ''
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function ScheduledPage() {
  const { user } = useStore()
  const userId = user?.id ?? 1
  const qc = useQueryClient()
  const [zoom, setZoom] = useState(null)
  const [editing, setEditing] = useState({ id: null, value: '' })

  const { data: posts = [], isLoading } = useQuery({
    queryKey: ['scheduled', userId],
    queryFn: () => listScheduled(userId).then(r => r.data),
    enabled: !!userId,
  })

  const cancelMutation = useMutation({
    mutationFn: deleteScheduled,
    onSuccess: () => { qc.invalidateQueries(['scheduled']); toast.success('تم إلغاء الجدولة') },
    onError: () => toast.error('حدث خطأ'),
  })

  const timeMutation = useMutation({
    mutationFn: ({ id, value }) => updateScheduledTime(id, new Date(value).toISOString()),
    onSuccess: () => {
      qc.invalidateQueries(['scheduled'])
      setEditing({ id: null, value: '' })
      toast.success('تم تعديل الوقت')
    },
    onError: () => toast.error('تعذّر تعديل الوقت'),
  })

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <CalendarClock size={24} className="text-primary-600" /> المجدولة
          </h1>
          <p className="text-gray-500">{posts.length} منشور مجدول للنشر على فيسبوك</p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-20">جاري التحميل...</div>
      ) : posts.length === 0 ? (
        <div className="text-center text-gray-400 py-20">
          <CalendarClock size={40} className="mx-auto mb-3 opacity-30" />
          <p>لا توجد منشورات مجدولة بعد</p>
          <p className="text-sm mt-1">اعتمدي منشوراً من أي حملة ليُجدول تلقائياً، أو اطلبي من «المساعد الذكي» جدولته</p>
        </div>
      ) : (
        <div className="space-y-3">
          {posts.map(sp => (
            <div key={sp.id} className="card flex items-start gap-4">
              {/* Image / placeholder */}
              {sp.image_url
                ? <img src={sp.image_url} alt="" onClick={() => setZoom(sp.image_url)}
                    className="w-20 h-20 object-cover rounded-xl flex-shrink-0 cursor-zoom-in hover:opacity-90 transition-opacity" />
                : <div className="w-20 h-20 bg-gray-100 rounded-xl flex items-center justify-center flex-shrink-0">
                    <ImageIcon size={22} className="text-gray-300" />
                  </div>}

              {/* Content */}
              <div className="flex-1 min-w-0">
                {editing.id === sp.id ? (
                  <div className="flex items-center gap-2 mb-1.5">
                    <input type="datetime-local" className="input !py-1 !text-sm w-auto"
                      value={editing.value}
                      onChange={e => setEditing(ed => ({ ...ed, value: e.target.value }))} />
                    <button onClick={() => timeMutation.mutate(editing)} disabled={!editing.value || timeMutation.isPending}
                      className="text-emerald-600 hover:text-emerald-700" title="حفظ"><Check size={18} /></button>
                    <button onClick={() => setEditing({ id: null, value: '' })}
                      className="text-gray-400 hover:text-gray-600" title="إلغاء"><X size={18} /></button>
                  </div>
                ) : (
                  <div className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary-700 bg-primary-50 rounded-full px-2.5 py-1 mb-1.5">
                    <Clock size={12} /> {formatWhen(sp)}
                    <button onClick={() => setEditing({ id: sp.id, value: toLocalInput(sp.scheduled_at) })}
                      className="text-primary-500 hover:text-primary-700 mr-1" title="تعديل الوقت"><Pencil size={12} /></button>
                  </div>
                )}
                {sp.hook && <p className="font-semibold text-gray-900 truncate">{sp.hook}</p>}
                {sp.caption && <p className="text-sm text-gray-600 line-clamp-2">{sp.caption}</p>}
                {sp.cta && <p className="text-xs text-primary-600 font-medium mt-0.5">👉 {sp.cta}</p>}
                {Array.isArray(sp.hashtags) && sp.hashtags.length > 0 && (
                  <p className="text-xs text-primary-400 mt-0.5">{sp.hashtags.join('  ')}</p>
                )}
              </div>

              {/* Status + cancel */}
              <div className="flex flex-col items-end gap-2 flex-shrink-0">
                <span className="text-xs bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full font-medium">
                  {sp.status === 'scheduled' ? 'مجدول' : sp.status}
                </span>
                <button onClick={() => cancelMutation.mutate(sp.id)}
                  className="text-red-400 hover:text-red-600 transition-colors" title="إلغاء الجدولة">
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <ImageLightbox src={zoom} onClose={() => setZoom(null)} />
    </div>
  )
}
