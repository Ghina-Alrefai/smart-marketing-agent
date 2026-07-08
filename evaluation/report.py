"""
مولّد تقرير HTML لنتيجة التقييم — ملف مستقل يُفتح في المتصفح.
"""
from __future__ import annotations

import html

GATE_BADGE = {
    "pass": ("✓ مُمرَّر", "#103226", "#36d399"),
    "fail": ("✗ رسوب", "#3a1418", "#f87272"),
    "pending": ("… معلّق", "#332a0d", "#fbbd23"),
}
METHOD_LABEL = {"rule": "قاعدي", "judge": "حَكَم لغوي", "human": "بشري"}


def _esc(x) -> str:
    return html.escape(str(x if x is not None else ""))


def render_html(result: dict) -> str:
    post = result["post"]
    rows = ""
    for d in result["dimensions"]:
        if d["status"] == "scored":
            s = f'<b>{d["score"]}</b>/5'
            contrib = d["contribution"]
            opacity = ""
        else:
            s = '<span style="color:#717aa6">معلّق</span>'
            contrib = "—"
            opacity = ' style="opacity:.55"'
        rows += (
            f'<tr{opacity}><td>{_esc(d["name"])} '
            f'<span class="m">{METHOD_LABEL.get(d["method"], d["method"])}</span></td>'
            f'<td>{d["layer"]}</td><td>{d["weight"]}</td><td>{s}</td>'
            f'<td>{contrib}</td><td class="note">{_esc(d["note"])}</td></tr>'
        )

    gate_rows = ""
    for g in result["gates"]:
        label, bg, fg = GATE_BADGE.get(g["status"], GATE_BADGE["pending"])
        gate_rows += (
            f'<tr><td>{_esc(g["name"])}</td>'
            f'<td><span class="badge" style="background:{bg};color:{fg}">{label}</span></td>'
            f'<td class="note">{_esc(g["note"])}</td></tr>'
        )

    pct = result["effective_pct"]
    return f"""<!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>تقرير تقييم المنشور</title><style>
body{{margin:0;background:#0f1220;color:#e8eaf2;font-family:Segoe UI,Tahoma,sans-serif;line-height:1.8}}
.wrap{{max-width:920px;margin:0 auto;padding:34px 20px 70px}}
h1{{font-size:24px}} h2{{font-size:19px;border-bottom:2px solid #6c8bff;padding-bottom:8px;margin-top:34px}}
.kpi{{text-align:center;background:#171a2b;border:1px solid #2a2f48;border-radius:16px;padding:26px;margin:20px 0}}
.score{{font-size:56px;font-weight:800;color:{result['band_color']};line-height:1}}
.band{{margin-top:8px;color:{result['band_color']};font-weight:700}}
.bar{{height:12px;background:#0b0e18;border-radius:7px;overflow:hidden;border:1px solid #2a2f48;max-width:480px;margin:16px auto}}
.bar>i{{display:block;height:100%;width:{pct}%;background:linear-gradient(90deg,#6c8bff,#36d399)}}
.meta{{color:#9aa0b8;font-size:14px;margin-top:10px}}
table{{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}}
th,td{{padding:9px 11px;text-align:right;border-bottom:1px solid #2a2f48}}
th{{background:#1d2138}} tr:hover td{{background:#1b2036}}
.m{{font-size:11px;color:#aebbff;background:#1a2142;border:1px solid #2c3a78;border-radius:5px;padding:1px 6px;margin-right:4px}}
.note{{color:#9aa0b8;font-size:13px}}
.badge{{padding:2px 9px;border-radius:7px;font-size:12px;font-weight:700}}
.card{{background:#171a2b;border:1px solid #2a2f48;border-radius:14px;padding:16px 20px;margin:14px 0}}
.callout{{border-right:4px solid #fbbd23;background:#1c1a10;padding:12px 16px;border-radius:10px;font-size:14px}}
.post p{{margin:6px 0}} .lbl{{color:#6c8bff;font-weight:700}}
</style></head><body><div class="wrap">
<h1>📊 تقرير تقييم منشور — المنصة: {_esc(post.get('platform','—'))}</h1>

<div class="kpi">
  <div class="score">{pct}%</div>
  <div class="band">{_esc(result['band_label'])}</div>
  <div class="bar"><i></i></div>
  <div class="meta">الحالة: <b>{_esc(result['final_status'])}</b><br>
  تغطية التقييم الآلي: <b>{result['coverage_pct']}%</b> من الوزن الكلّي
  {'(تقييم كامل ✓)' if result['complete'] else '— الباقي معلّق للمرحلة 2 (الحَكَم اللغوي)'}<br>
  النسبة المبدئية على المُقيَّم: <b>{result['provisional_pct']}%</b></div>
</div>

<div class="card post"><span class="lbl">المنشور المُقيَّم:</span>
<p><b>Hook:</b> {_esc(post.get('hook'))}</p>
<p><b>Caption:</b> {_esc(post.get('caption'))}</p>
<p><b>CTA:</b> {_esc(post.get('cta'))}</p>
<p><b>Hashtags:</b> {_esc(' '.join(post.get('hashtags') or []))}</p></div>

<h2>البوابات الحرجة</h2>
<table><tr><th>البوابة</th><th>النتيجة</th><th>الملاحظة</th></tr>{gate_rows}</table>

<h2>الأبعاد الموزونة</h2>
<table><tr><th>البُعد</th><th>الطبقة</th><th>الوزن</th><th>الدرجة</th><th>المساهمة</th><th>الملاحظة</th></tr>
{rows}</table>

<div class="callout">النسبة <b>{pct}%</b> = مجموع مساهمات الأبعاد المُقيَّمة (الدرجة÷5 × الوزن)
مُطبَّعة على وزنها، بعد تطبيق البوابات الحرجة. الأبعاد المعلّقة ستُحسب في المرحلة 2.</div>
</div></body></html>"""


def save_report(result: dict, path: str = "evaluation_report.html") -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(result))
    return path
