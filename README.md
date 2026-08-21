# SmartSocial AI — النسخة المدمجة الكاملة (v1.2.0)

نسخة متكاملة من مشروع الفريق مع **Stable Brand DNA v1.1.0** و**Adaptive Memory**، مع الحفاظ على الـworkflow المتفق عليه:

`Orchestrator → Brand → Strategy → Product → Idea → Candidates → Content/Design → Evaluation → Human Approval → Schedule → Performance → Memory`

الدمج لا يستبدل منسّق الفريق أو واجهته. أضيفت طبقة ذكاء خلفية موحّدة تجعل كل فكرة تنتج ثلاثة مرشحين مضبوطين، تتحقق من بنيتهم وهوية البراند، ترتبهم بنموذج خاص بالصفحة عندما يكون متاحاً، تصلح المحاولة الضعيفة ضمن حد معلوم، ثم تحفظ مسار القرار كاملاً للمراجعة.

## أهم ضمانات التصميم

- **Brand DNA ثابت**: الهوية والنبرة والألوان والقيود مصدرها ملف الإصدار أو إدخال المستخدم، ولا تعدّلها الذاكرة تلقائياً.
- **Adaptive Memory محكومة**: الأداء الفعلي يولّد Evidence؛ الأنماط تحتاج دعماً متكرراً وتحققاً؛ السياسات تبدأ `draft` ولا تصبح `active` بلا اعتماد بشري.
- **الإنسان هو صاحب قرار النشر**: حتى المرشح الأعلى تقييماً يبقى `approved = false` إلى أن يضغط المستخدم اعتماد.
- **Cold Start صادق**: الصفحة الجديدة تعمل مباشرة بقواعد الهوية والتحقق البنيوي، من دون استعارة نموذج البراق، ومن دون احتمال نجاح أو SHAP وهمي.
- **تتبّع كامل**: كل منشور يحتفظ بالمرشحين الثلاثة، المرشح المختار، الإصدارات، الدرجات، السياسات المستخدمة، ومعرف trace.
- **توقف آمن**: إذا فشلت المحاولات الثلاث أو بقيت الدرجات تحت البوابة، تكون الحالة `needs_review` ولا يحدث نشر تلقائي.
- **تصميم بصري محكوم**: أصل بصري واحد هادئ لكل منشور؛ لا شبكات 3×3 أو Storyboard، ولا شعارات أو قوالب مولّدة عندما يوجد قالب مرفوع سيُركّب برمجياً.
- **إعادة محاولة آمنة**: الحملة الفاشلة قابلة لإعادة التوليد من الواجهة بعد إزالة نواتجها الجزئية غير المعتمدة، مع حماية الموافقات وبيانات الأداء من الحذف.

## البنية

```text
agents/                      وكلاء الفريق (مع محول Brand Agent الجديد)
api/                         FastAPI + مسارات الذكاء الجديدة
frontend/                    React/Vite + شاشة الذكاء والتعلم
workflows/campaign_pipeline.py  الـworkflow الوحيد للحملات
services/campaign_intelligence.py  دمج التوليد والتقييم والتصميم
services/brand_intelligence_service.py  تهيئة DNA وحالة الصفحة ونتائج الأداء
brand_dna/                   التنبؤ، SHAP، العقود، التحقق والإصلاح
adaptive_memory/             Evidence → Insight → Draft Policy → Activation
smart_social_contracts/      ملكية الميزات بين الوكلاء
artifacts/                   نماذج Al Boraq وModel Card وBrand Profile
outputs/                     أدلة OOF ونتائج التقييم التاريخية
schema/                      عقود JSON للإدخال/التعلّم
docs/                        شرح اللجنة، المعمارية، الاختبار، والـworkflow الأصلي
scripts/                     إعداد، تشغيل، preload، demo، وفحص الإصدار
```

## التشغيل السريع

المتطلبات: Python 3.11 أو 3.12، Node.js 18+، وذاكرة كافية لتحميل نماذج embeddings.

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
# ضع GOOGLE_API_KEY داخل .env
.\scripts\run.ps1
```

### Linux/macOS

```bash
chmod +x scripts/setup.sh scripts/run.sh
./scripts/setup.sh
# ضع GOOGLE_API_KEY داخل .env
./scripts/run.sh
```

بعد التشغيل:

- التطبيق: `http://localhost:8000`
- توثيق API: `http://localhost:8000/docs`
- واجهة التطوير (اختياري): `cd frontend && npm run dev`

قبل عرض دون إنترنت، شغّل مرة واحدة مع اتصال متاح:

```bash
python scripts/preload_models.py
```

## متغيرات البيئة المهمة

| المتغير | الغرض | الافتراضي |
|---|---|---|
| `GOOGLE_API_KEY` | Gemini للنص والصورة | مطلوب للتوليد الحقيقي |
| `GOOGLE_CLIENT_ID` | التحقق الخلفي من Google ID Token | مطلوب لدخول Google |
| `VITE_GOOGLE_CLIENT_ID` | إظهار زر Google في React؛ يجب أن يطابق القيمة السابقة | مطلوب لدخول Google |
| `SECRET_KEY` | توقيع جلسات الدخول | يجب تغييره في الإنتاج |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | حساب المشرف المحلي | قيم تطوير فقط؛ غيّر كلمة المرور |
| `GEMINI_MODEL` | نموذج النص | `gemini-2.5-flash` |
| `GEMINI_IMAGE_MODEL` | نموذج الصورة | `gemini-3.1-flash-image` |
| `DATABASE_URL` | قاعدة التطبيق | `sqlite:///./marketing_os.db` |
| `ADAPTIVE_MEMORY_DB` | مصدر حقيقة الذاكرة | `./outputs/adaptive_memory/app.db` |
| `BRAND_DNA_MODEL_BRAND_KEYS` | الصفحات التي لها نموذج مسجل | `al-boraq` |
| `BRAND_DNA_GENERATION_MAX_ATTEMPTS` | حد التوليد/الإصلاح | `3` |
| `BRAND_DNA_MIN_CANDIDATE_PROBABILITY` | بوابة النموذج | `0.50` |
| `COLD_START_MIN_TRAINING_POSTS` | الحد الإرشادي لبناء نموذج صفحة | `30` |
| `DEFAULT_SCHEDULE_HOUR` | ساعة الجدولة بعد الاعتماد | `20` |
| `LOG_LEVEL` | مستوى سجل التطبيق (`DEBUG/INFO/WARNING/ERROR`) | `INFO` |
| `LOG_DIR` | مجلد ملفات السجل | `./logs` |
| `LOG_TO_FILE` | حفظ السجل في ملف دوّار إضافةً إلى Terminal | `true` |
| `SQL_ECHO` | طباعة SQL الخام للتشخيص المحلي المؤقت فقط | `false` |

انسخ `.env.example` إلى `.env` ولا تضع المفاتيح داخل Git. بعد تعديل أي متغير
يبدأ بـ `VITE_` أعد بناء الواجهة عبر `cd frontend && npm run build`. يرفض الخادم
العمل في وضع `production` إذا بقي `SECRET_KEY` أو كلمة مرور المشرف على القيمة
التجريبية الافتراضية.

## تشخيص الأخطاء والـLogger

يعمل الـlogger تلقائياً عند تشغيل FastAPI. تظهر الأحداث في الـTerminal وتُحفظ في
`logs/app.log`، وكل طلب يحمل `request_id` يظهر أيضاً للمستخدم داخل رسالة الخطأ.
للمتابعة الحية:

```bash
tail -f logs/app.log
```

وفي Windows PowerShell:

```powershell
Get-Content .\logs\app.log -Wait -Tail 100
```

إذا فشل إنشاء البراند، ابحث في الملف عن رقم التتبع الظاهر في الواجهة. راجع
`docs/DEBUGGING_LOGGING_AR.md` للخطوات الكاملة وأسباب الفشل المعروفة.

## فحص النسخة

```bash
python scripts/verify_release.py
pytest -q
python scripts/committee_demo.py
cd frontend && npm run build
```

`committee_demo.py` ينشئ صفحة جديدة بلا تاريخ ويشغّل الحملة في `dry_run`؛ لا يستدعي Gemini ولا يدّعي احتمالاً إحصائياً.

## نقاط API الجديدة

| Method | Endpoint | الوظيفة |
|---|---|---|
| `POST` | `/api/v1/plans/{id}/regenerate` | تنظيف محاولة فاشلة غير معتمدة وإعادة توليدها بأمان |
| `GET` | `/api/v1/intelligence/brands/{id}/status` | حالة DNA والنموذج والذاكرة |
| `POST` | `/api/v1/intelligence/brands/{id}/initialize` | تهيئة ملف ثابت أو Cold Start |
| `GET` | `/api/v1/intelligence/brands/{id}/profile` | الملف الفعّال وإصداره |
| `POST` | `/api/v1/intelligence/brands/{id}/bootstrap-history` | إدخال دليل Al Boraq التاريخي بشكل idempotent |
| `POST` | `/api/v1/intelligence/brands/{id}/consolidate` | تجميع Evidence والتحقق من Insights |
| `POST` | `/api/v1/intelligence/brands/{id}/generate-policies` | إنشاء مسودات سياسات غير فعالة |
| `GET` | `/api/v1/intelligence/brands/{id}/policies` | عرض السياسات وحالاتها |
| `POST` | `/api/v1/intelligence/policies/{id}/activate` | اعتماد بشري صريح لسياسة |
| `POST` | `/api/v1/intelligence/posts/{id}/performance` | تسجيل نتيجة منشور بعد 24h/72h مثلاً |

## نتائج النموذج المضمّن

البيانات: 50 منشوراً من Al Boraq Telecom، موزعة 25 نجاح و25 فشل. التقييم OOF مع ضوابط لمنع التسرب.

| النموذج | Accuracy | F1 | ROC-AUC | Brier |
|---|---:|---:|---:|---:|
| Predesign | 0.58 | 0.604 | 0.675 | 0.222 |
| Multimodal | 0.56 | 0.577 | 0.677 | 0.223 |

هذه نتائج نموذج أولي على عينة صغيرة. الاحتمال يستخدم **للترتيب ودعم القرار** ولا يمثل ضمان أداء. وSHAP يشرح سلوك النموذج ولا يثبت علاقة سببية.

## ملفات الشرح

- `docs/COMMITTEE_GUIDE_AR.md`: شرح العرض من الصفر حتى النهاية وأسئلة متوقعة.
- `docs/INTEGRATION_ARCHITECTURE.md`: ما أضيف وما استبدل وما بقي ثابتاً.
- `docs/TESTING_GUIDE_AR.md`: سيناريوهات الاختبار والتحضير للعرض.
- `docs/full_workflow.html`: الـworkflow البصري الأصلي المتفق عليه مع الفريق.

إصدار التطبيق: `1.2.0-merged` — أغسطس 2026. إصدار Brand DNA المضمّن: `1.1.0`.
