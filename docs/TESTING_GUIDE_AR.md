# دليل الاختبار والتحضير لعرض اللجنة

## 1. فحص الإصدار بلا مكتبات خارجية

```bash
python scripts/verify_release.py
```

يتحقق من الملفات الأساسية، صلاحية syntax لكل ملفات Python، إصدار Model Card، عدد بيانات التدريب، ويطبع SHA‑256 للنموذجين.

## 2. اختبارات Brand DNA وAdaptive Memory

```bash
pytest -q
```

الحزمة تتضمن 15 اختباراً أساسياً تغطي:

- صحة سجل ملكية الميزات.
- عقد Brand‑DNA → Adaptive Memory.
- ثبات Event ID عند إعادة المعالجة.
- idempotent ingestion ومنع تكرار الدليل.
- عدم تكوين سياسة من منشور واحد.
- تعلم تاريخي من 50 سجلاً OOF.
- بقاء السياسات Draft حتى الاعتماد.
- حقن السياسات Active فقط في prompt.
- إصلاح دفعة مرشحين ناقصة في المحاولة التالية.
- التوقف `needs_review` عند انخفاض كل النتائج.
- منع سياسة Draft من التأثير في التوليد.

## 3. اختبار الصفحة الجديدة دون API خارجي

```bash
python scripts/committee_demo.py
```

النتيجة المتوقعة:

- إنشاء صفحة جديدة ومنتج وحملة في قاعدة مستقلة.
- حالة الصفحة `cold_start`.
- إنشاء منشور اختبار عبر pipeline نفسه.
- ثلاثة مرشحين موثقين.
- `predicted_success_probability = null`.
- `feature_attributions = []`.
- `approved = false` حتى تدخل الإنسان.

## 4. فحص Backend

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

افتح `http://localhost:8000/docs` واختبر بالترتيب:

1. إنشاء مستخدم.
2. إنشاء Brand.
3. إضافة Product.
4. `POST /intelligence/brands/{id}/initialize`.
5. إنشاء Content Plan.
6. تشغيل generation.
7. متابعة status ثم posts.
8. التأكد أن `approved=false`.
9. اعتماد منشور من الواجهة والتأكد من الجدولة.

## 5. فحص Frontend

```bash
cd frontend
npm ci
npm run build
```

تحقق يدوياً من:

- شاشة البراند وحفظ الحقول.
- شاشة المنتجات.
- إنشاء حملة.
- ظهور ثلاثة مرشحين وBadge حالة الذكاء في تفاصيل الحملة.
- شاشة «الذكاء والتعلّم».
- تعطيل زر bootstrap للصفحة الجديدة.
- عدم تفعيل أي Draft تلقائياً.
- تحديث حالة السياسة بعد الضغط على اعتماد وتفعيل.

## 6. اختبار Al Boraq الحقيقي

قبل الاختبار المتصل:

```bash
python scripts/preload_models.py
```

ثم:

1. أنشئ Brand اسمه Al Boraq Telecom أو البراق.
2. هيئ الذكاء؛ يجب أن تكون الحالة `model_ready`.
3. شغّل `bootstrap-history` مرتين؛ الثانية يجب أن تعيد inserted=0 وduplicates>0.
4. نفذ consolidate.
5. أنشئ draft policies.
6. راجع policy ثم فعّل واحدة فقط.
7. أنشئ حملة جديدة وتحقق من `adaptive_memory_applied` عند تطابق السياق.
8. راقب predesign وmultimodal؛ لا تفسرهما كضمان.

## 7. اختبار المرشحين المكسورين

استخدم FakeClient أو prompt test يعيد أولاً عنصرين فقط، ثم ثلاثة عناصر صحيحة. يجب أن يظهر:

```text
attempt 1: validation / rejected
attempt 2: quality_gate / accepted
```

إذا بقيت الاستجابة خاطئة ثلاث مرات:

```text
status=needs_review
approved=false
scheduled_at=null
```

## 8. اختبار تسجيل الأداء

بعد نشر منشور مع تنبؤ حقيقي، أرسل:

```json
{
  "observation_window": "24h",
  "actual_success": true,
  "reactions": 120,
  "comments": 20,
  "shares": 10,
  "reach": 5000,
  "clicks": 80
}
```

إلى `/intelligence/posts/{post_id}/performance`.

تحقق من:

- إنشاء snapshot واحد.
- حساب weighted engagement عند غيابه: `reactions + 2×comments + 3×shares`.
- إدخال Evidence فقط إذا كان للمنشور تنبؤ حقيقي وSHAP.
- عند إعادة نفس window: `duplicate=true`.
- في Cold Start: تخزين metrics فقط مع ملاحظة عدم اختلاق SHAP.

## 9. خطة عرض احتياطية

جهّز قبل اللجنة:

- `.env` صحيحاً واختبر المفتاح.
- شغّل preload للنماذج.
- نفذ build للواجهة.
- احتفظ بلقطات شاشة من حملة ناجحة.
- احتفظ بقاعدة demo جاهزة.
- جرّب `committee_demo.py` دون إنترنت.
- لا تعتمد على تنزيل encoder أو npm packages أثناء العرض.

## 10. معيار القبول النهائي

النسخة مقبولة عندما:

- تمر 15/15 من اختبارات النواة.
- يمر verify_release.
- يبنى frontend بنجاح في بيئة كاملة الاعتماديات.
- ينتهي cold-start demo بلا API خارجي.
- لا توجد سياسة Active من دون approved_by وapproved_at.
- لا يوجد منشور approved قبل إجراء المستخدم.
- لا تظهر probability أو SHAP لصفحة بلا نموذج خاص.
