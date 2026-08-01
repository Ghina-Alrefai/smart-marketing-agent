"""
مُجرِّب الشات في الطرفية — تحدّثي مع الأوركستريتور مباشرة.

    python -m agents.orchestrator.chat_cli            # وضع تجريبي (بلا Gemini، بلا تكلفة)
    python -m agents.orchestrator.chat_cli --real     # وضع حقيقي (يستدعي Gemini فعلاً)
    python -m agents.orchestrator.chat_cli --user 1 --brand 1

اكتبي 'خروج' أو 'exit' للإنهاء. الجلسة تُحفظ تلقائياً بين الرسائل.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from agents.orchestrator.orchestrator_agent import handle_message


def _arg(flag, default):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def main() -> None:
    dry = "--real" not in sys.argv
    user_id = int(_arg("--user", "1"))
    brand_id = int(_arg("--brand", "1"))
    mode = "تجريبي (stub)" if dry else "حقيقي (Gemini)"

    print("=" * 60)
    print(f"  💬 مُجرِّب شات AI Marketing OS — الوضع: {mode}")
    print(f"  user_id={user_id} · brand_id={brand_id} · فيسبوك فقط")
    print("  اكتب رسالتك (أو 'خروج' للإنهاء). أمثلة:")
    print("   • صمّم صورة لمنتج HOCO")
    print("   • اكتبلي منشور عن لابتوب ASUS")
    print("   • اعمل خطة 7 ايام")
    print("=" * 60)

    session_id = None
    while True:
        try:
            msg = input("\n👤 أنت: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 مع السلامة")
            break
        if not msg:
            continue
        if msg.lower() in ("خروج", "exit", "quit"):
            print("👋 مع السلامة")
            break

        r = handle_message(user_id, brand_id, msg, session_id=session_id, dry_run=dry)
        session_id = r["session_id"]

        print(f"🤖 الوكيل [{r['type']}]: {r['message']}")

        if r.get("options"):
            print("   الخيارات:")
            for i, o in enumerate(r["options"], 1):
                print(f"     {i}) {o['label']}")
            print("   (اكتب رقم الخيار أو اسم المنتج)")
        if r.get("data"):
            print(f"   📦 النتيجة: {r['data']}")


if __name__ == "__main__":
    main()
