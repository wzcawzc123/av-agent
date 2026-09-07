#!/usr/bin/env python3
"""端到端实测：随机设备入库 → 数据库 → 智能匹配 → 对话 → 生成，输出实测报告。

运行: python scripts/e2e_verify.py
说明: 入库/匹配/数据库/引擎生成为真实链路；LLM 分类提取用内置 Fake（演示数据流，
      真实使用配置模型后由 LLM 完成同等工作）；对话展示未配置模型时的引导行为。
"""
import io
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings

settings.ensure_dirs()
settings.PORT = 8160 if settings.PORT == 8000 else settings.PORT

# 清掉测试可能写入的假模型配置，演示干净的"未配置模型"引导
try:
    model_json = os.path.join(settings.DATA_DIR, "model.json")
    if os.path.exists(model_json):
        os.remove(model_json)
except Exception:
    pass

# ---------- 随机设备参数（演示数据） ----------
FAKE_DEVICES = [
    {"name": "专业功放", "model": "AMP-300P", "brand": "测试音响", "spec": "300W 8Ω 2通道",
     "market_price": 3800},
    {"name": "专业功放", "model": "AMP-600P", "brand": "测试音响", "spec": "600W 8Ω 2通道",
     "market_price": 5600},
    {"name": "吸顶音箱", "model": "SPK-8C", "brand": "测试音响", "spec": "8寸 吸顶 60W",
     "market_price": 880},
    {"name": "无线手持话筒", "model": "MIC-U2", "brand": "测试音响", "spec": "一拖二 UHF",
     "market_price": 2600},
    {"name": "LED显示屏 P2", "model": "LED-P2-100", "brand": "测试显示", "spec": "P2 全彩 100寸",
     "market_price": 48000},
]


def make_xlsx() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["产品名称", "型号", "品牌", "规格", "市场价"])
    for d in FAKE_DEVICES:
        ws.append([d["name"], d["model"], d["brand"], d["spec"], d["market_price"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


class FakeIngestProvider:
    """演示 LLM 分类/提取（真实使用中由配置的模型完成）。"""

    async def chat(self, messages, temperature=0.7):
        user = messages[-1].content if messages else ""
        if "文件内容" in user:
            return '{"type":"products","title":"测试设备清单","confidence":0.98}'
        return '{"products": [{"name":"%s","model":"%s","brand":"%s","spec":"%s","market_price":%d}]}' % (
            FAKE_DEVICES[0]["name"], FAKE_DEVICES[0]["model"],
            FAKE_DEVICES[0]["brand"], FAKE_DEVICES[0]["spec"], FAKE_DEVICES[0]["market_price"])


def main():
    print("=" * 64)
    print("  AV Agent 端到端实测")
    print("=" * 64)

    # 1) 起服务
    import uvicorn

    from app.main import app as fastapi_app

    cfg = uvicorn.Config(fastapi_app, host="127.0.0.1", port=settings.PORT, log_level="error")
    server = uvicorn.Server(cfg)
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.time() + 15
    import httpx

    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{settings.PORT}/api/health").status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.4)
    base = f"http://127.0.0.1:{settings.PORT}"
    print(f"\n[1] 服务已启动: {base}")

    # 2) 智能入库（mock LLM 分类/提取，演示数据流）
    import app.api.routes_ingest as ri

    ri.get_provider = lambda cfg2: FakeIngestProvider()
    ri.load_model_config = lambda: {"provider": "demo", "api_key": "demo"}
    files = {"file": ("测试设备清单.xlsx", make_xlsx(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = httpx.post(f"{base}/api/ingest", files=files, data={"target": "auto"})
    d = r.json()
    print(f"[2] 智能入库: ok={d.get('ok')} type={d.get('type')} message={d.get('message')}")
    print(f"    识别标题: {d.get('title')}")

    # 3) 数据库工作方式（products 表结构与入库行）
    from app.db.session import get_session
    from app.db.models import Product

    with get_session() as s:
        row = s.query(Product).filter_by(model="AMP-300P").first()
        print("[3] 数据库(SQLite products 表):")
        print(f"    入库行: id={row.id} | {row.name} | {row.model} | {row.brand} | 市场价 {row.market_price}")
        print(f"    字段: name/model/brand/description/params_json/base_price/market_price/category/system/role_tags/active")
        print(f"    去重键: model 唯一（重复上传自动跳过）")
        total = s.query(Product).count()
        print(f"    当前产品总数: {total}")

    # 4) 智能匹配（核心新功能）
    for q in ["300W 功放", "8寸音箱", "P2 LED 屏", "无线话筒"]:
        r = httpx.get(f"{base}/api/products/match", params={"q": q})
        ms = r.json().get("matches", [])
        top = ms[0] if ms else None
        if top:
            p = top["product"]
            print(f"[4] 匹配『{q}』→ {p['name']} {p['model']}（{top['score']:.0f} 分, {top['reason']}）")
        else:
            print(f"[4] 匹配『{q}』→ 无结果")

    # 5) 对话可答性（未配置模型 → 引导；配模型走 LLM）
    r = httpx.post(f"{base}/api/chat", json={"text": "你能干什么？"})
    d = r.json()
    print(f"[5] 对话『你能干什么？』→ {d.get('reply', '')[:60]}（need_config={d.get('need_config')}）")

    # 6) 引擎直通生成（无 LLM 也能出文件）
    r = httpx.post(f"{base}/api/chat", json={"text": "led屏 5米宽 3米高"})
    d = r.json()
    f = (d.get("files") or [None])[0]
    print(f"[6] 引擎直通生成: engine={d.get('engine')} | 文件存在={f and os.path.isfile(f)} | {d.get('reply', '')[:40]}")

    server.should_exit = True
    print("\n实测完成。真实使用中: 配置模型后入库分类/提取/对话/方案生成全部由 LLM 完成，" +
          "匹配/去重/引擎/数据库为确定性逻辑。")


if __name__ == "__main__":
    main()
