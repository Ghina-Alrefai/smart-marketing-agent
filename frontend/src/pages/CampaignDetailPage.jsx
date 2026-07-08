import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CheckCircle, XCircle, Clock, Loader, Hash, Image, Trash2 } from 'lucide-react'
import { getPlan, listPosts, approvePost, deletePlan } from '../api/client'

const STATUS_BADGE = {
  approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-red-50 text-red-700',
  reviewing: 'bg-amber-50 text-amber-700',
  draft: 'bg-gray-100 text-gray-600',
}

export default function CampaignDetailPage() {
  const { id } = useParams()
  const planId = parseInt(id)
  const qc = useQueryClient()
  const navigate = useNavigate()

  const { data: plan } = useQuery({
    queryKey: ['plan', planId],
    queryFn: () => getPlan(planId).then(r => r.data),
    refetchInterval: (query) => query.state.data?.status === 'generating' ? 3000 : false,
  })

  const { data: posts = [], isLoading } = useQuery({
    queryKey: ['posts', planId],
    queryFn: () => listPosts(planId).then(r => r.data),
    refetchInterval: plan?.status === 'generating' ? 4000 : false,
  })

  const approveMutation = useMutation({
    mutationFn: ({ postId, approved }) => approvePost(postId, approved),
    onSuccess: () => qc.invalidateQueries(['posts', planId]),
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePlan(planId),
    onSuccess: () => {
      qc.invalidateQueries(['plans'])
      toast.success('تم حذف الحملة')
      navigate('/campaigns')
    },
    onError: () => toast.error('فشل الحذف'),
  })

  const handleDelete = () => {
    if (window.confirm('هل أنتِ متأكدة من حذف هذه الحملة وجميع منشوراتها؟')) {
      deleteMutation.mutate()
    }
  }

  const approvedCount = posts.filter(p => p.approved).length
  const isGenerating = plan?.status === 'generating'

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {plan?.campaign_name || `حملة #${planId}`}
            </h1>
            <p className="text-gray-500 mt-1">{plan?.days} أيام · {plan?.platform}</p>
          </div>
          <div className="flex items-center gap-3">
            {isGenerating && (
              <div className="flex items-center gap-2 bg-blue-50 text-blue-700 px-4 py-2 rounded-xl text-sm font-semibold">
                <Loader size={16} className="animate-spin" />
                جاري التوليد...
              </div>
            )}
            <button
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-red-600 bg-red-50 hover:bg-red-100 transition-colors disabled:opacity-50"
            >
              <Trash2 size={16} />
              {deleteMutation.isPending ? 'جاري الحذف...' : 'حذف الحملة'}
            </button>
          </div>
        </div>

        {/* Progress bar */}
        {posts.length > 0 && (
          <div className="mt-4 p-4 bg-gray-50 rounded-xl">
            <div className="flex justify-between text-sm text-gray-600 mb-2">
              <span>{approvedCount} منشور معتمد من {posts.length}</span>
              <span>{Math.round((approvedCount / posts.length) * 100)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${(approvedCount / posts.length) * 100}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* Generating placeholder */}
      {isGenerating && posts.length === 0 && (
        <div className="text-center py-20">
          <div className="inline-flex flex-col items-center gap-4">
            <div className="w-16 h-16 bg-primary-50 rounded-full flex items-center justify-center">
              <Sparkles size={28} className="text-primary-600 animate-pulse" />
            </div>
            <div>
              <p className="font-semibold text-gray-800">الذكاء الاصطناعي يعمل...</p>
              <p className="text-sm text-gray-400 mt-1">يتم تحليل البراند وبناء الاستراتيجية وكتابة المحتوى</p>
            </div>
          </div>
        </div>
      )}

      {/* Posts grid */}
      {posts.length > 0 && (
        <div className="space-y-6">
          {posts.map(post => (
            <div key={post.id} className={`card border-2 transition-all ${post.approved ? 'border-emerald-200' : 'border-transparent'}`}>
              <div className="flex items-start gap-4">
                {/* Image */}
                <div className="flex-shrink-0 w-40 h-40 bg-gray-100 rounded-xl overflow-hidden">
                  {post.image_url ? (
                    <img
                      src={post.image_url}
                      alt="Post"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none'
                        e.target.nextSibling.style.display = 'flex'
                      }}
                    />
                  ) : null}
                  <div
                    className="w-full h-full flex-col items-center justify-center text-gray-400 text-xs text-center p-2 gap-1"
                    style={{ display: post.image_url ? 'none' : 'flex' }}
                  >
                    <Image size={28} className="opacity-40" />
                    <span>{post.image_url ? 'تعذّر تحميل الصورة' : 'لا توجد صورة'}</span>
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full">
                      اليوم {post.day_number}
                    </span>
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
                      {post.post_type}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_BADGE[post.status] || STATUS_BADGE.draft}`}>
                      {post.status === 'approved' ? 'معتمد' : post.status === 'rejected' ? 'مرفوض' : 'قيد المراجعة'}
                    </span>
                  </div>

                  {post.hook && (
                    <p className="font-bold text-gray-900 text-sm mb-1">🎯 {post.hook}</p>
                  )}

                  <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap line-clamp-4">
                    {post.caption}
                  </p>

                  {post.cta && (
                    <p className="text-primary-600 font-semibold text-sm mt-2">👉 {post.cta}</p>
                  )}

                  {post.hashtags?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {post.hashtags.slice(0, 6).map(tag => (
                        <span key={tag} className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">#{tag.replace('#', '')}</span>
                      ))}
                    </div>
                  )}

                  {post.review_notes && (
                    <p className="text-xs text-gray-400 mt-2 italic">ملاحظات المراجعة: {post.review_notes}</p>
                  )}
                </div>

                {/* Approval buttons */}
                <div className="flex flex-col gap-2 flex-shrink-0">
                  <button
                    onClick={() => approveMutation.mutate({ postId: post.id, approved: true })}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition-all
                      ${post.approved ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'}`}
                  >
                    <CheckCircle size={16} />
                    اعتماد
                  </button>
                  <button
                    onClick={() => approveMutation.mutate({ postId: post.id, approved: false })}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition-all
                      ${!post.approved && post.status === 'rejected' ? 'bg-red-600 text-white' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}
                  >
                    <XCircle size={16} />
                    رفض
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Mini icon used in the loading state above
function Sparkles({ size, className }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5z"/><path d="M5 3l.5 1.5L7 5l-1.5.5L5 7l-.5-1.5L3 5l1.5-.5z"/><path d="M19 13l.5 1.5L21 15l-1.5.5L19 17l-.5-1.5L17 15l1.5-.5z"/>
    </svg>
  )
}
