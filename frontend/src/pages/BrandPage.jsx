import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Save, Upload, Plus, Trash2, ChevronDown, ChevronUp, ImageIcon, Type, Layout, Eye } from 'lucide-react'
import useStore from '../store'
import {
  createBrand, updateBrand, listBrands,
  uploadBrandTemplate,
  addBrandExample, listBrandExamples,
  uploadDesignExample, deleteExample,
} from '../api/client'

const TONE_OPTIONS   = ['ودّي','احترافي','شبابي','فاخر','مضحك','جريء','بسيط']
const STYLE_OPTIONS  = ['قصير','قصصي','مباشر','عاطفي']
const VISUAL_OPTIONS = ['داكن','عصري','ملوّن','نظيف','بسيط','حيوي','رسمي']

const emptyForm = () => ({
  brand_name:'', business_description:'',
  tone_of_voice:[], content_style:[], visual_style:[],
  brand_colors:'#6366f1', target_audience:'', language:'ar',
  must_use_words:'', forbidden_words:'', preferred_cta:'',
})

function brandToForm(b) {
  if (!b) return emptyForm()
  const split = v => v ? v.split('،').map(s=>s.trim()).filter(Boolean) : []
  return {
    brand_name: b.brand_name||'', business_description: b.business_description||'',
    tone_of_voice: split(b.tone_of_voice), content_style: split(b.content_style),
    visual_style: split(b.visual_style),
    brand_colors: (b.brand_colors||[]).join(', '),
    target_audience: b.target_audience||'', language: b.language||'ar',
    must_use_words: (b.must_use_words||[]).join(', '),
    forbidden_words: (b.forbidden_words||[]).join(', '),
    preferred_cta: b.preferred_cta||'',
  }
}

function Section({ id, open, onToggle, title, icon: Icon, children }) {
  return (
    <div className="card overflow-hidden p-0">
      <button className="w-full flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
        onClick={() => onToggle(id)}>
        <div className="flex items-center gap-2 font-bold text-gray-800">
          <Icon size={16} className="text-primary-500" />{title}
        </div>
        {open ? <ChevronUp size={15} className="text-gray-400"/> : <ChevronDown size={15} className="text-gray-400"/>}
      </button>
      {open && <div className="px-6 pb-6 pt-2 space-y-4 border-t border-gray-50">{children}</div>}
    </div>
  )
}

export default function BrandPage() {
  const { user, setActiveBrandId } = useStore()
  const qc = useQueryClient()

  const [activeBrand, setActiveBrand]   = useState(null)
  const [form, setForm]                 = useState(emptyForm())
  const [showAdd, setShowAdd]           = useState(false)
  const [openSection, setOpenSection]   = useState('basic')
  const [newTextEx, setNewTextEx]       = useState('')
  const [designFiles, setDesignFiles]   = useState([])
  const [templateFile, setTemplateFile] = useState(null)
  const [templatePreview, setTemplatePreview] = useState(null)

  const { data: brands=[] } = useQuery({
    queryKey: ['brands', user?.id],
    queryFn: () => listBrands(user?.id).then(r=>r.data),
    enabled: !!user?.id,
  })

  const { data: examples=[] } = useQuery({
    queryKey: ['brand-examples', activeBrand?.id],
    queryFn: () => listBrandExamples(activeBrand.id).then(r=>r.data),
    enabled: !!activeBrand?.id,
  })

  const textExamples   = examples.filter(e=>e.example_type==='post')
  const designExamples = examples.filter(e=>e.example_type==='design')

  useEffect(() => {
    if (brands.length > 0 && !activeBrand) { setActiveBrand(brands[0]); setForm(brandToForm(brands[0])) }
  }, [brands])

  const select = (b) => { setActiveBrand(b); setForm(brandToForm(b)); setShowAdd(false); setTemplateFile(null); setTemplatePreview(null) }
  const toggle = (field, val) => setForm(f => ({ ...f, [field]: f[field].includes(val) ? f[field].filter(v=>v!==val) : [...f[field],val] }))
  const toggleSection = (id) => setOpenSection(s => s===id ? null : id)

  const handleTemplateChange = (e) => {
    const file = e.target.files[0]; if (!file) return
    setTemplateFile(file)
    setTemplatePreview(URL.createObjectURL(file))
  }

  const saveMutation = useMutation({
    mutationFn: async (data) => {
      const payload = {
        ...data,
        tone_of_voice:  data.tone_of_voice.join('، '),
        content_style:  data.content_style.join('، '),
        visual_style:   data.visual_style.join('، '),
        brand_colors:   data.brand_colors.split(',').map(c=>c.trim()).filter(Boolean),
        must_use_words: data.must_use_words.split(',').map(w=>w.trim()).filter(Boolean),
        forbidden_words:data.forbidden_words.split(',').map(w=>w.trim()).filter(Boolean),
      }
      const res = activeBrand && !showAdd ? await updateBrand(activeBrand.id, payload) : await createBrand(user.id, payload)
      const brand = res.data
      if (templateFile) await uploadBrandTemplate(brand.id, templateFile)
      return brand
    },
    onSuccess: (brand) => {
      setActiveBrandId(brand.id); setActiveBrand(brand)
      qc.invalidateQueries(['brands']); setShowAdd(false); setTemplateFile(null)
      toast.success('تم حفظ البراند ✅')
    },
    onError: () => toast.error('حدث خطأ'),
  })

  const addTextMutation = useMutation({
    mutationFn: () => addBrandExample(activeBrand.id, { example_type:'post', content:newTextEx }),
    onSuccess: () => { qc.invalidateQueries(['brand-examples', activeBrand.id]); setNewTextEx('') },
  })

  const uploadDesignMutation = useMutation({
    mutationFn: async (files) => { for (const f of files) await uploadDesignExample(activeBrand.id, f) },
    onSuccess: () => { qc.invalidateQueries(['brand-examples', activeBrand.id]); setDesignFiles([]); toast.success('تم رفع التصاميم ✅') },
    onError: () => toast.error('فشل الرفع'),
  })

  const delExMutation = useMutation({
    mutationFn: deleteExample,
    onSuccess: () => qc.invalidateQueries(['brand-examples', activeBrand?.id]),
  })

  const currentTemplate = templatePreview || activeBrand?.template_url || null

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">البراندات</h1>
          <p className="text-gray-500 text-sm mt-0.5">هوية علامتك التجارية هي قلب النظام</p>
        </div>
        <button className="btn-primary flex items-center gap-2"
          onClick={() => { setActiveBrand(null); setForm(emptyForm()); setShowAdd(true); setTemplateFile(null); setTemplatePreview(null) }}>
          <Plus size={16}/> براند جديد
        </button>
      </div>

      {brands.length > 0 && (
        <div className="flex gap-2 mb-6 overflow-x-auto pb-1">
          {brands.map(b => (
            <button key={b.id} onClick={() => select(b)}
              className={`px-4 py-2 rounded-xl text-sm font-semibold whitespace-nowrap border transition-all
                ${activeBrand?.id===b.id && !showAdd ? 'bg-primary-600 text-white border-primary-600' : 'border-gray-200 text-gray-600 hover:border-primary-300'}`}>
              {b.brand_name}
            </button>
          ))}
          {showAdd && <span className="px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">+ جديد</span>}
        </div>
      )}

      <div className="space-y-4">

        {/* Basic */}
        <Section id="basic" open={openSection==='basic'} onToggle={toggleSection} title="المعلومات الأساسية" icon={Type}>
          <div>
            <label className="label">اسم البراند *</label>
            <input className="input" value={form.brand_name} onChange={e=>setForm(f=>({...f,brand_name:e.target.value}))} placeholder="مثال: براند فيشن"/>
          </div>
          <div>
            <label className="label">وصف النشاط التجاري</label>
            <textarea className="input" rows={3} value={form.business_description} onChange={e=>setForm(f=>({...f,business_description:e.target.value}))} placeholder="ماذا تبيع؟ من هم عملاؤك؟"/>
          </div>
          <div>
            <label className="label">الجمهور المستهدف</label>
            <input className="input" value={form.target_audience} onChange={e=>setForm(f=>({...f,target_audience:e.target.value}))} placeholder="مثال: شباب 18-35 مهتمون بالموضة"/>
          </div>
        </Section>

        {/* Personality */}
        <Section id="personality" open={openSection==='personality'} onToggle={toggleSection} title="شخصية البراند" icon={Type}>
          <p className="text-xs text-gray-400 -mt-1">يمكن اختيار أكثر من خيار في كل قسم</p>
          {[
            {label:'نبرة الصوت',    field:'tone_of_voice', options:TONE_OPTIONS},
            {label:'أسلوب المحتوى', field:'content_style', options:STYLE_OPTIONS},
            {label:'أسلوب التصاميم',field:'visual_style',  options:VISUAL_OPTIONS},
          ].map(({label,field,options}) => (
            <div key={field}>
              <label className="label">{label}</label>
              <div className="flex flex-wrap gap-2">
                {options.map(opt => (
                  <button key={opt} type="button" onClick={()=>toggle(field,opt)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all
                      ${form[field].includes(opt) ? 'bg-primary-600 text-white border-primary-600' : 'border-gray-200 text-gray-600 hover:border-primary-300'}`}>
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </Section>

        {/* Writing */}
        <Section id="writing" open={openSection==='writing'} onToggle={toggleSection} title="قواعد الكتابة" icon={Type}>
          <div>
            <label className="label">ألوان البراند (مفصولة بفاصلة)</label>
            <input className="input" dir="ltr" value={form.brand_colors} onChange={e=>setForm(f=>({...f,brand_colors:e.target.value}))} placeholder="#6366f1, #1e293b"/>
          </div>
          <div>
            <label className="label">كلمات يجب استخدامها</label>
            <input className="input" value={form.must_use_words} onChange={e=>setForm(f=>({...f,must_use_words:e.target.value}))} placeholder="حصري, جديد, عرض"/>
          </div>
          <div>
            <label className="label">كلمات ممنوعة</label>
            <input className="input" value={form.forbidden_words} onChange={e=>setForm(f=>({...f,forbidden_words:e.target.value}))} placeholder="رخيص, مجاني"/>
          </div>
          <div>
            <label className="label">CTA المفضل</label>
            <input className="input" value={form.preferred_cta} onChange={e=>setForm(f=>({...f,preferred_cta:e.target.value}))} placeholder="تسوق الآن، اطلب عبر الرابط..."/>
          </div>
        </Section>

        {/* Template */}
        <Section id="template" open={openSection==='template'} onToggle={toggleSection} title="قالب التصميم" icon={Layout}>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
            <p className="font-bold mb-1">كيف يعمل القالب؟</p>
            <p>ارفع صورة PNG تحتوي على لوغو البراند ومعلومات التواصل وأي عناصر ثابتة.</p>
            <p className="mt-1">المنطقة الشفافة في القالب ستُملأ تلقائياً بالصورة التي يولّدها الذكاء الاصطناعي.</p>
            <p className="mt-1 font-semibold">اجعل القالب 1080×1080 بكسل للحصول على أفضل نتيجة.</p>
          </div>

          <div className="flex gap-6 items-start">
            {/* Preview */}
            <div className="flex-shrink-0">
              <p className="text-xs text-gray-500 mb-2 text-center font-medium">معاينة القالب</p>
              <div className="w-48 h-48 rounded-2xl border-2 border-dashed border-gray-200 overflow-hidden bg-gray-50 flex items-center justify-center">
                {currentTemplate ? (
                  <img src={currentTemplate} alt="template" className="w-full h-full object-contain"/>
                ) : (
                  <div className="text-center text-gray-400 p-4">
                    <Layout size={32} className="mx-auto mb-2 opacity-30"/>
                    <p className="text-xs">لا يوجد قالب</p>
                    <p className="text-xs mt-0.5 opacity-70">سيُستخدم الصورة كما هي</p>
                  </div>
                )}
              </div>
            </div>

            {/* Upload */}
            <div className="flex-1">
              <label className="label">رفع قالب التصميم (PNG شفاف)</label>
              <label className="flex flex-col items-center gap-3 cursor-pointer border-2 border-dashed border-gray-200 rounded-xl p-6 hover:border-primary-300 hover:bg-primary-50/30 transition-all">
                <Upload size={28} className="text-gray-300"/>
                <div className="text-center">
                  <p className="text-sm font-semibold text-gray-700">
                    {templateFile ? templateFile.name : 'اضغط لاختيار القالب'}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">PNG فقط — يجب أن تكون المنطقة الداخلية شفافة</p>
                </div>
                <input type="file" accept="image/png" className="hidden" onChange={handleTemplateChange}/>
              </label>
              {templateFile && (
                <p className="text-xs text-emerald-600 mt-2 font-medium">✅ سيتم رفع القالب عند الحفظ</p>
              )}
              {activeBrand?.template_url && !templateFile && (
                <p className="text-xs text-gray-500 mt-2">✅ يوجد قالب محفوظ — ارفع جديداً لاستبداله</p>
              )}
            </div>
          </div>
        </Section>

        {/* Examples — only for saved brands */}
        {activeBrand && !showAdd && (
          <Section id="examples" open={openSection==='examples'} onToggle={toggleSection} title="أمثلة للذكاء الاصطناعي" icon={Eye}>
            <p className="text-xs text-gray-500 -mt-1">كلما أضفت أمثلة أكثر، كان الذكاء الاصطناعي أدق في محاكاة أسلوبك</p>

            {/* Text examples */}
            <div>
              <label className="label flex items-center gap-1.5"><Type size={13}/> منشورات نصية سابقة ({textExamples.length})</label>
              <div className="space-y-2 mb-2 max-h-48 overflow-y-auto">
                {textExamples.map(ex=>(
                  <div key={ex.id} className="flex items-start gap-2 bg-gray-50 rounded-xl p-3 border border-gray-100">
                    <p className="text-sm text-gray-700 flex-1 leading-relaxed">{ex.content}</p>
                    <button onClick={()=>delExMutation.mutate(ex.id)} className="text-red-400 hover:text-red-600 flex-shrink-0"><Trash2 size={13}/></button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <textarea className="input flex-1 text-sm" rows={2} value={newTextEx} onChange={e=>setNewTextEx(e.target.value)} placeholder="الصق هنا نص منشور سابق..."/>
                <button className="btn-primary self-end px-3 py-2" onClick={()=>addTextMutation.mutate()} disabled={!newTextEx.trim()||addTextMutation.isPending}>
                  <Plus size={15}/>
                </button>
              </div>
            </div>

            {/* Design examples */}
            <div>
              <label className="label flex items-center gap-1.5 mt-2"><ImageIcon size={13}/> تصاميم سابقة كمرجع ({designExamples.length})</label>
              <p className="text-xs text-gray-400 mb-2">صور تصاميمك السابقة — يتعلم منها الذكاء الاصطناعي الأسلوب البصري</p>
              {designExamples.length > 0 && (
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {designExamples.map(ex=>(
                    <div key={ex.id} className="relative group aspect-square rounded-xl overflow-hidden border border-gray-200">
                      <img src={ex.image_url} alt="design" className="w-full h-full object-cover"/>
                      <button onClick={()=>delExMutation.mutate(ex.id)}
                        className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Trash2 size={10}/>
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <label className="flex items-center gap-3 cursor-pointer border-2 border-dashed border-gray-200 rounded-xl p-3 hover:border-primary-300 transition-colors">
                <Upload size={18} className="text-gray-300 flex-shrink-0"/>
                <div>
                  <p className="text-sm text-gray-600">{designFiles.length>0 ? `${designFiles.length} صورة مختارة` : 'ارفع تصاميم مرجعية'}</p>
                  <p className="text-xs text-gray-400">PNG, JPG — متعدد</p>
                </div>
                <input type="file" accept="image/*" multiple className="hidden" onChange={e=>setDesignFiles(Array.from(e.target.files))}/>
              </label>
              {designFiles.length > 0 && (
                <button className="btn-primary w-full mt-2 flex items-center justify-center gap-2"
                  onClick={()=>uploadDesignMutation.mutate(designFiles)} disabled={uploadDesignMutation.isPending}>
                  <Upload size={15}/>
                  {uploadDesignMutation.isPending ? 'جاري الرفع...' : `رفع ${designFiles.length} تصميم`}
                </button>
              )}
            </div>
          </Section>
        )}

        <button className="btn-primary w-full flex items-center justify-center gap-2 py-3"
          onClick={()=>saveMutation.mutate(form)} disabled={saveMutation.isPending||!form.brand_name}>
          <Save size={18}/>
          {saveMutation.isPending ? 'جاري الحفظ...' : showAdd ? 'إنشاء البراند' : 'حفظ التعديلات'}
        </button>
      </div>
    </div>
  )
}
