import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Sparkles, Package, Megaphone, ChevronLeft, TrendingUp } from 'lucide-react'
import useStore from '../store'
import { listPlans, listProducts, listBrands } from '../api/client'

export default function Dashboard() {
  const { user } = useStore()

  const { data: brandsData } = useQuery({
    queryKey: ['brands', user?.id],
    queryFn: () => listBrands(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const { data: productsData } = useQuery({
    queryKey: ['products', user?.id],
    queryFn: () => listProducts(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const { data: plansData } = useQuery({
    queryKey: ['plans', user?.id],
    queryFn: () => listPlans(user?.id).then(r => r.data),
    enabled: !!user?.id,
  })

  const stats = [
    { label: 'البراندات', value: brandsData?.length ?? 0, icon: Sparkles, color: 'text-violet-600 bg-violet-50', to: '/brand' },
    { label: 'المنتجات', value: productsData?.length ?? 0, icon: Package, color: 'text-blue-600 bg-blue-50', to: '/products' },
    { label: 'الحملات', value: plansData?.length ?? 0, icon: Megaphone, color: 'text-emerald-600 bg-emerald-50', to: '/campaigns' },
  ]

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">مرحباً، {user?.name || 'مستخدم'} 👋</h1>
        <p className="text-gray-500 mt-1">إليك ملخص نشاطك التسويقي اليوم</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-6 mb-10">
        {stats.map(({ label, value, icon: Icon, color, to }) => (
          <Link key={label} to={to} className="card hover:shadow-md transition-shadow group">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-3xl font-bold text-gray-900">{value}</p>
                <p className="text-gray-500 text-sm mt-1">{label}</p>
              </div>
              <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${color}`}>
                <Icon size={22} />
              </div>
            </div>
            <div className="flex items-center gap-1 mt-4 text-sm text-primary-600 opacity-0 group-hover:opacity-100 transition-opacity">
              <span>عرض التفاصيل</span>
              <ChevronLeft size={16} />
            </div>
          </Link>
        ))}
      </div>

      {/* Quick actions */}
      <h2 className="font-bold text-gray-900 mb-4">إجراءات سريعة</h2>
      <div className="grid grid-cols-2 gap-4">
        <Link to="/brand" className="card border-2 border-dashed border-primary-200 hover:border-primary-400 transition-colors text-center cursor-pointer group">
          <Sparkles size={28} className="text-primary-400 group-hover:text-primary-600 mx-auto mb-2 transition-colors" />
          <p className="font-semibold text-gray-800">إعداد البراند</p>
          <p className="text-xs text-gray-400 mt-1">أضف هوية علامتك التجارية</p>
        </Link>
        <Link to="/campaigns/new" className="card border-2 border-dashed border-emerald-200 hover:border-emerald-400 transition-colors text-center cursor-pointer group">
          <Megaphone size={28} className="text-emerald-400 group-hover:text-emerald-600 mx-auto mb-2 transition-colors" />
          <p className="font-semibold text-gray-800">إنشاء حملة</p>
          <p className="text-xs text-gray-400 mt-1">توليد محتوى جاهز للنشر</p>
        </Link>
      </div>
    </div>
  )
}
