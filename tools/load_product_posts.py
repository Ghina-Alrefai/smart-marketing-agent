"""يستورد المنشورات المرجعية من ملف Excel ويربطها بمنتجات الأدمن.

الاستخدام:
    python tools/load_product_posts.py <ملف.xlsx> [--replace] [--dry-run]

    --replace : يحذف المنشورات المرجعية السابقة للمستخدم قبل الإدراج.
    --dry-run : يعرض ما سيحدث دون الكتابة في قاعدة البيانات.
"""
from __future__ import annotations

import io
import sys

from database.models import Product, ProductPost, User
from database.session import SessionLocal
from tools.post_import import parse_posts_xlsx


def main() -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        print(__doc__)
        return 2
    path, replace, dry = args[0], "--replace" in flags, "--dry-run" in flags

    posts, errors = parse_posts_xlsx(open(path, "rb").read())
    for e in errors:
        print("تحذير:", e)
    if not posts:
        print("لا شيء لاستيراده.")
        return 1

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "super_admin").first()
        if admin is None:
            print("لم يُعثر على حساب المشرف."); return 1

        rows = (
            db.query(Product.id, Product.title)
            .filter(Product.user_id == admin.id)
            .order_by(Product.id)
            .all()
        )
        # رقم المنتج (1..N) → المعرّف الحقيقي
        ref_to_id = {i: r[0] for i, r in enumerate(rows, start=1)}
        id_to_title = {r[0]: r[1] for r in rows}

        valid, skipped = [], []
        for p in posts:
            pid = ref_to_id.get(p["product_ref"])
            if pid is None:
                skipped.append(
                    f"سطر {p['row']}: رقم المنتج {p['product_ref']} خارج المدى 1..{len(rows)}"
                )
                continue
            valid.append((pid, p))

        for s in skipped:
            print("تخطّي:", s)

        print(f"\nصالح للإدراج: {len(valid)} منشوراً | متخطّى: {len(skipped)}")
        per_product: dict[int, int] = {}
        for pid, _ in valid:
            per_product[pid] = per_product.get(pid, 0) + 1
        print("\nالتوزيع على المنتجات:")
        for i, r in enumerate(rows, start=1):
            n = per_product.get(r[0], 0)
            mark = "  " if n else "!!"
            print(f" {mark} [{i:>2}] id={r[0]:<4} {str(r[1])[:44]:<44} → {n} منشور")

        if dry:
            print("\n(dry-run — لم تُكتب أي بيانات)")
            return 0

        if replace:
            n = (
                db.query(ProductPost)
                .filter(ProductPost.user_id == admin.id)
                .delete(synchronize_session=False)
            )
            print(f"\nحُذف {n} منشوراً مرجعياً سابقاً.")

        for pid, p in valid:
            db.add(ProductPost(
                user_id=admin.id,
                product_id=pid,
                source_ref=str(p["product_ref"]),
                post_type=p["post_type"],
                post_goal=p["post_goal"],
                hook=p["hook"],
                caption=p["caption"],
                cta=p["cta"],
                hashtags=p["hashtags"],
                image_prompt=p["image_prompt"],
                image_url=p["image_url"],
                notes=p["notes"],
            ))
        db.commit()
        total = db.query(ProductPost).filter(ProductPost.user_id == admin.id).count()
        print(f"\nأُدرج {len(valid)} منشوراً. الإجمالي الآن: {total}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
