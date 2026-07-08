# 🤖 AI Marketing OS

نظام تشغيل تسويقي مبني على الذكاء الاصطناعي — Multi-Agent System باستخدام Google ADK + Gemini.

---

## 🏗 هيكل المشروع

```
ai_marketing_os/
│
├── agents/                  # وكلاء الذكاء الاصطناعي
│   ├── brand/               # Brand Agent
│   ├── strategy/            # Strategy Agent
│   ├── product/             # Product Analysis Agent
│   ├── content/             # Content Agent
│   ├── design/              # Design Agent
│   └── review/              # Review Agent
│
├── tools/                   # أدوات مشتركة (DB, Image Gen)
├── services/                # خدمات (LLM service)
├── prompts/                 # جميع الـ Prompts مركزياً
├── database/                # SQLAlchemy Models + Session
├── workflows/               # Pipeline الرئيسي
├── api/                     # FastAPI Routers + Schemas
├── frontend/                # React + Tailwind + Zustand
├── uploads/                 # ملفات مرفوعة + صور مولّدة
├── main.py                  # نقطة دخول FastAPI
├── config.py                # إعدادات التطبيق
└── requirements.txt
```

---

## 🚀 التثبيت والتشغيل

### 1. المتطلبات الأساسية
- Python 3.11+
- Node.js 18+

### 2. إعداد البيئة

```bash
# استنساخ المشروع
git clone https://github.com/Ghina-Alrefai/smart-marketing-agent.git
cd smart-marketing-agent

# إنشاء virtual environment
python -m venv venv
source venv/bin/activate      # Linux/Mac
# أو: venv\Scripts\activate   # Windows

# تثبيت المكتبات
pip install -r requirements.txt
```

### 3. إعداد متغيرات البيئة

```bash
cp .env.example .env
```

افتح `.env` وضع مفتاح Google API الخاص بك:

```
GOOGLE_API_KEY=your_key_here
```

للحصول على مفتاح: https://aistudio.google.com/app/apikey

### 4. تشغيل الـ Backend

```bash
uvicorn main:app --reload --port 8000
```

API docs متاحة على: http://localhost:8000/docs

### 5. تشغيل الـ Frontend

```bash
cd frontend
npm install
npm run dev
```

التطبيق على: http://localhost:5173

---

## 🔄 كيف يعمل النظام؟

```
المستخدم يُنشئ حملة
       ↓
[Brand Agent] تحليل هوية البراند
       ↓
[Strategy Agent] بناء خطة محتوى {N} أيام
       ↓
لكل يوم في الخطة:
  ├── [Product Analysis Agent] تحليل المنتج
  ├── [Content Agent] كتابة Hook + Caption + CTA + Hashtags
  ├── [Design Agent] بناء Image Prompt + توليد الصورة
  └── [Review Agent] مراجعة الجودة والموافقة
       ↓
عرض النتائج للمستخدم مع Approval Workflow
```

---

## 📡 API Endpoints الرئيسية

| Method | URL | الوصف |
|--------|-----|-------|
| POST | `/api/v1/users/` | إنشاء مستخدم |
| POST | `/api/v1/brands/?user_id=` | إنشاء براند |
| PATCH | `/api/v1/brands/{id}` | تحديث البراند |
| POST | `/api/v1/brands/{id}/logo` | رفع اللوغو |
| GET | `/api/v1/products/user/{user_id}` | قائمة المنتجات |
| POST | `/api/v1/products/?user_id=` | إضافة منتج |
| POST | `/api/v1/plans/?user_id=` | إنشاء خطة محتوى |
| POST | `/api/v1/plans/{id}/generate` | بدء التوليد |
| GET | `/api/v1/plans/{id}/status` | متابعة الحالة |
| GET | `/api/v1/plans/{id}/posts` | جميع المنشورات |
| PATCH | `/api/v1/plans/posts/{id}/approve` | اعتماد/رفض منشور |

---

## 🧠 الـ Agents

| Agent | المهمة |
|-------|--------|
| **Brand Agent** | تحليل هوية البراند وبناء Brand Guidelines |
| **Strategy Agent** | بناء خطة محتوى يومية متنوعة ومتوازنة |
| **Product Analysis Agent** | استخراج الزوايا التسويقية المثلى للمنتج |
| **Content Agent** | كتابة Hook + Caption + CTA + Hashtags |
| **Design Agent** | بناء Image Prompt + توليد الصورة بـ Gemini |
| **Review Agent** | مراجعة الجودة وتقييم التوافق مع البراند |

---

## 🔑 متغيرات البيئة

| المتغير | الوصف | القيمة الافتراضية |
|---------|-------|------------------|
| `GOOGLE_API_KEY` | مفتاح Google AI API | مطلوب |
| `DATABASE_URL` | رابط قاعدة البيانات | `sqlite:///./marketing_os.db` |
| `UPLOAD_DIR` | مجلد الملفات المرفوعة | `./uploads` |
| `GEMINI_MODEL` | نموذج النصوص | `gemini-2.0-flash` |
| `GEMINI_IMAGE_MODEL` | نموذج الصور | `gemini-2.0-flash-exp-image-generation` |

---

## 📦 التقنيات المستخدمة

**Backend:** Python · FastAPI · Google ADK · SQLAlchemy · SQLite

**AI:** Google Gemini 2.0 Flash (نصوص + صور)

**Frontend:** React 18 · Vite · Tailwind CSS · Zustand · React Query · React Router

---

## 🗺 Roadmap

- [x] Brand Onboarding
- [x] Multi-Agent Content Pipeline
- [x] Image Generation
- [x] Human Approval Workflow
- [ ] Publish to Social Media
- [ ] Analytics Dashboard
- [ ] Multi-brand Support
- [ ] Scheduled Posts
