import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Plus, Trash2, Package, Upload, ImageIcon } from 'lucide-react'
import useStore from '../store'
import { createProduct, listProducts, deleteProduct, uploadProductImage } from '../api/client'

const emptyForm = { title: '', description: '', price: '', category: '' }

export default function ProductsPage() {
  const { user } = useStore()
  const qc = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)

  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products', user?.id],
    queryFn: () => listProducts(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const addMutation = useMutation({
    mutationFn: async (data) => {
      const res = await createProduct(user.id, {
        ...data,
        price: data.price ? parseFloat(data.price) : null,
      })
      if (imageFile) {
        await uploadProductImage(res.data.id, imageFile)
      }
      return res
    },
    onSuccess: () => {
      qc.invalidateQueries(['products'])
      setForm(emptyForm)
      setImageFile(null)
      setImagePreview(null)
      setShowForm(false)
      toast.success('تم إضافة المنتج ✅')
    },
    onError: () => toast.error('حدث خطأ'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteProduct,
    onSuccess: () => { qc.invalidateQueries(['products']); toast.success('تم حذف المنتج') },
  })

  const handleImageChange = (e) => {
    const file = e.target.files[0]
    if (!file) return
    setImageFile(file)
    setImagePreview(URL.createObjectURL(file))
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">المنتجات</h1>
          <p className="text-gray-500">{products.length} منتج مضاف</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => setShowForm(s => !s)}>
          <Plus size={18} /> إضافة منتج
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div className="card mb-6 border-primary-200 border">
          <h3 className="font-bold text-gray-800 mb-4">منتج جديد</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="label">اسم المنتج *</label>
              <input className="input" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="مثال: عباية سوداء فاخرة" />
            </div>
            <div className="col-span-2">
              <label className="label">الوصف</label>
              <textarea className="input" rows={2} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div>
              <label className="label">السعر ($)</label>
              <input className="input" type="number" value={form.price} onChange={e => setForm(f => ({ ...f, price: e.target.value }))} placeholder="0.00" />
            </div>
            <div>
              <label className="label">الفئة</label>
              <input className="input" value={form.category} onChange={e => setForm(f => ({ ...f, category: e.target.value }))} placeholder="أزياء، إكسسوارات..." />
            </div>

            {/* Product image upload */}
            <div className="col-span-2">
              <label className="label">صورة المنتج <span className="text-gray-400 font-normal">(اختياري — ستُستخدم في التصميم)</span></label>
              <label className="flex items-center gap-3 cursor-pointer border-2 border-dashed border-gray-200 rounded-xl p-3 hover:border-primary-300 transition-colors">
                {imagePreview
                  ? <img src={imagePreview} className="h-16 w-16 object-cover rounded-lg" />
                  : <div className="h-16 w-16 bg-gray-100 rounded-lg flex items-center justify-center"><ImageIcon size={24} className="text-gray-300" /></div>
                }
                <div>
                  <p className="text-sm font-medium text-gray-700">{imageFile ? imageFile.name : 'اختر صورة المنتج'}</p>
                  <p className="text-xs text-gray-400 mt-0.5">PNG, JPG, WEBP</p>
                </div>
                <Upload size={18} className="text-gray-400 mr-auto" />
                <input type="file" accept="image/*" className="hidden" onChange={handleImageChange} />
              </label>
            </div>
          </div>

          <div className="flex gap-3 mt-4">
            <button className="btn-primary" onClick={() => addMutation.mutate(form)} disabled={!form.title || addMutation.isPending}>
              {addMutation.isPending ? 'جاري الإضافة...' : 'إضافة'}
            </button>
            <button className="btn-secondary" onClick={() => { setShowForm(false); setImageFile(null); setImagePreview(null) }}>إلغاء</button>
          </div>
        </div>
      )}

      {/* Products grid */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-20">جاري التحميل...</div>
      ) : products.length === 0 ? (
        <div className="text-center text-gray-400 py-20">
          <Package size={40} className="mx-auto mb-3 opacity-30" />
          <p>لا توجد منتجات بعد</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {products.map(product => (
            <div key={product.id} className="card group relative overflow-hidden">
              {/* Image */}
              {product.image_url ? (
                <img src={product.image_url} alt={product.title} className="w-full h-36 object-cover rounded-xl mb-3" />
              ) : (
                <div className="w-full h-36 bg-gray-100 rounded-xl mb-3 flex items-center justify-center">
                  <Package size={28} className="text-gray-300" />
                </div>
              )}

              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900 truncate">{product.title}</p>
                  {product.price != null && (
                    <p className="text-sm text-primary-600 font-bold mt-0.5">${product.price}</p>
                  )}
                  {product.category && <p className="text-xs text-gray-400 mt-0.5">{product.category}</p>}
                </div>
                <button
                  onClick={() => deleteMutation.mutate(product.id)}
                  className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-all mr-1 flex-shrink-0"
                >
                  <Trash2 size={16} />
                </button>
              </div>

              {/* Post count badge */}
              {product.post_count > 0 && (
                <div className="mt-2">
                  <span className="text-xs bg-primary-50 text-primary-600 px-2 py-0.5 rounded-full font-medium">
                    {product.post_count} منشور
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
