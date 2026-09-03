"""产品库批量导入脚本（CLI）。

用法：
    python scripts/import_products_cli.py <Excel文件1> [Excel文件2 ...]

说明：
- 支持 MAXHUB 全产品清单 / 音视频报价清单等常见格式（多 sheet、分类段、名称继承）；
- 型号重复自动跳过，不覆盖已有产品；
- 价格字段一律留空（0），后续导入带价格的清单时再补充；
- 默认写入应用数据目录的 avagent.db，可用 --db 指定其他 SQLite 文件。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from app.config import settings
from app.db.session import get_engine, get_session
from app.db.models import Base, Product
from app.db.migrate import ensure_schema
from app.db.product_importer import import_products_v2


def main():
    parser = argparse.ArgumentParser(description="导入产品库 Excel")
    parser.add_argument("files", nargs="+", help="产品 Excel 文件路径")
    parser.add_argument("--db", default=settings.DB_PATH, help="目标 SQLite 数据库（默认应用数据目录）")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    Base.metadata.create_all(engine)
    ensure_schema(engine)

    total_inserted = total_skipped = 0
    with get_session(engine) as s:
        for f in args.files:
            if not os.path.exists(f):
                print(f"[跳过] 文件不存在: {f}")
                continue
            r = import_products_v2(f, s)
            total_inserted += r["inserted"]
            total_skipped += r["skipped"]
            print(f"[完成] {os.path.basename(f)}: 新增 {r['inserted']}，跳过重复 {r['skipped']}")
        count = s.query(Product).count()
    print(f"\n合计新增 {total_inserted}，跳过重复 {total_skipped}，库内产品总数 {count}")


if __name__ == "__main__":
    main()
