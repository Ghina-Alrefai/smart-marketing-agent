# دليل الـLogger وتشخيص فشل البراند والحملات

## النتيجة المتوقعة

عند تشغيل التطبيق، يكتب الخادم السجل في مكانين معاً:

1. نافذة الـTerminal التي شُغّل منها FastAPI.
2. الملف `logs/app.log` مع تدوير تلقائي عند بلوغ 5 MB والاحتفاظ بخمس نسخ.

كل طلب API يحصل على `request_id` مستقل. يعيده الخادم في ترويسة
`X-Request-ID`، وتعرضه الواجهة ضمن رسالة الخطأ. بذلك يمكن مطابقة الخطأ الظاهر
للمستخدم مع السطر والـstack trace الصحيحين في السجل.

## التشغيل

من جذر المشروع:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

لا يحتاج الـlogger إلى مكتبة إضافية؛ فهو يستخدم `logging` المدمج في Python.

ضع القيم التالية داخل `.env` أثناء التطوير:

```env
APP_ENV=development
LOG_LEVEL=INFO
LOG_DIR=./logs
LOG_TO_FILE=true
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=5
SQL_ECHO=false
```

استخدم `LOG_LEVEL=DEBUG` عند الحاجة إلى تفاصيل إضافية. لا تجعل
`SQL_ECHO=true` إلا مؤقتاً وعلى جهاز التطوير، لأن SQL الخام قد يتضمن قيماً من
قاعدة البيانات.

## متابعة السجل لحظياً

Linux أو macOS:

```bash
tail -f logs/app.log
```

Windows PowerShell:

```powershell
Get-Content .\logs\app.log -Wait -Tail 100
```

ثم حاول إنشاء البراند مرة أخرى. ستظهر سلسلة مشابهة:

```text
INFO     | smartsocial.brands | request_id=... | brand.create_started user_id=1
INFO     | smartsocial.brands | request_id=... | brand.create_succeeded user_id=1 brand_id=3
INFO     | smartsocial        | request_id=... | request.completed method=POST path=/api/v1/brands/ status=201 ...
```

وعند الفشل ستظهر `brand.create_failed` أو `brand.create_rejected` مع نفس رقم
التتبع الذي تعرضه الواجهة.

## أسباب فشل إنشاء البراند التي أصبحت واضحة الآن

### 1. المستخدم المحلي قديم بعد حذف قاعدة البيانات

الواجهة تحفظ المستخدم في `localStorage`، بينما بيانات المستخدم الفعلية موجودة
في `marketing_os.db`. إذا حُذف ملف القاعدة وبقي المتصفح مفتوحاً، يحاول إنشاء
البراند باستخدام `user_id` لم يعد موجوداً.

المعالجة الجديدة تتحقق من المستخدم عند فتح التطبيق، تمسح المرجع المحلي القديم،
وتطلب إنشاء المستخدم من شاشة **الإعدادات**. كما يرفض الخادم إنشاء Brand يتيم
ويرجع `404` برسالة عربية واضحة.

### 2. الطلب لا يطابق Schema

يرجع الخادم `422` ويسجل `request.validation_failed` مع اسم الحقل والسبب. تعرض
الواجهة تفاصيل الحقول بدلاً من الرسالة العامة «حدث خطأ».

### 3. تعارض أو خطأ في قاعدة البيانات

- `409`: تعارض سلامة بيانات، مثل مرجع غير صالح أو قيد فريد.
- `500`: خطأ قاعدة بيانات أو خطأ داخلي؛ ابحث عن `request_id` في السجل لرؤية
  الـstack trace.

### 4. تم إنشاء البراند لكن فشل رفع القالب

إنشاء البراند ورفع PNG طلبان منفصلان. الواجهة الآن توضح صراحةً إذا تم حفظ
البراند وحدث الفشل في مرحلة رفع القالب فقط، فلا يعيد المستخدم إنشاء نسخة مكررة.

## اختبار API مباشرة

بعد إنشاء مستخدم رقمه `1`، يمكن اختبار المسار من Swagger عبر
`http://localhost:8000/docs` أو باستخدام curl:

```bash
curl -i -X POST "http://localhost:8000/api/v1/brands/?user_id=1" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: manual-brand-test" \
  -d '{"brand_name":"Test Brand","brand_colors":["#6366f1"],"language":"ar"}'
```

ابحث بعدها عن `manual-brand-test` داخل `logs/app.log`.

## الملفات المسؤولة

- `logging_config.py`: إعداد Console وRotating File وربط `request_id`.
- `main.py`: middleware لكل الطلبات وتسجيل أخطاء التحقق والاستثناءات.
- `database/session.py`: rollback تلقائي، تفعيل SQLite foreign keys، وسجل migrations.
- `api/routers/brands.py`: سجل مفصل لمسار إنشاء/تحديث البراند ورفع القالب.
- `frontend/src/api/client.js`: استخراج رسالة الخادم ورقم التتبع وتسجيل خطأ منظم في Console المتصفح.
- `frontend/src/components/AppLayout.jsx`: كشف `user_id` المحلي القديم.

لا يسجل التطبيق مفتاح Gemini ولا جسم الطلب كاملاً. مع ذلك، يجب التعامل مع ملفات
السجل كبيانات تشغيل داخلية وعدم نشرها في Git أو مشاركتها علناً.

## تشخيص فشل توليد الحملة

توليد الحملة يعمل كمهمة خلفية. لذلك نجاح طلب
`POST /plans/{id}/generate` يعني أن المهمة **بدأت** فقط، ولا يعني أن Gemini
أكملها. تحفظ النسخة الحالية داخل `ContentPlan`:

- `current_stage`: آخر مرحلة وصل إليها التوليد.
- `error_message`: المرحلة ونوع الاستثناء ورسالة المزود.

وتعرضهما صفحة الحملات وصفحة تفاصيل الحملة. كما يكتب السجل Stack Trace تحت:

```text
smartsocial.llm      | llm.call_failed
smartsocial.campaign | campaign.generation_failed
```

لاختبار الإعداد من PowerShell دون طباعة المفتاح نفسه:

```powershell
python -c "from config import settings; print('key_loaded=', bool(settings.GOOGLE_API_KEY), 'model=', settings.GEMINI_MODEL)"
python -c "from services.llm_service import call_llm; print(call_llm('Return only the word OK'))"
```

الأمر الثاني يعرض خطأ Gemini الحقيقي مباشرةً، مثل مفتاح غير صالح أو موديل غير
متاح أو تجاوز الحصة. عند اختبار الـworkflow ابدأ بثلاثة منتجات فقط؛ اختيار 72
منتجاً يضخم مدخل الاستراتيجية بلا فائدة في حملة مدتها ثلاثة أيام.
