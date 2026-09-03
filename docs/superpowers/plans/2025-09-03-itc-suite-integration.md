# itc 工具包补全方案：会议/广播/LED/偏离表 集成到 av-agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 itc 方案制作工具包（会议清单、广播清单、LED、偏离表）的 VBA 宏逻辑逆向移植为 av-agent 的 Python 数据驱动引擎，并比原工具有语义增强与规则可配置化。

**Architecture:** 四个独立引擎模块（deviation/meeting/broadcast/led），输入统一为结构化 dict，输出统一为清单行列表；选型规则从 VBA 硬编码迁移到 SQLite 规则表（数据驱动，可后台维护）；偏离匹配采用「字符评分 + 语义模型（可选 LLM）」双通道；全部经 pytest TDD 实现，最后接线到现有 FastAPI API 与 excel_generator。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / openpyxl / pytest / sqlite3（本地库）

**Spec:** docs/superpowers/plans/2025-09-03-itc-suite-integration.md（本文档，逆向结论见文末附录 A）

## Global Constraints

- 数据库：沿用现有 SQLite（data/avagent.db），所有新表通过 SQLAlchemy Base.metadata.create_all 自动创建，不手写 SQL DDL。
- 型号匹配：必须精确到 model 字段（products.model 唯一索引）；模糊匹配只作为兜底，结果必须标记 confidence。
- 价格：引擎输出的价格列默认留空（0），由用户后续单独填价，禁止引擎自行推断价格。
- 编码解析：会议清单输入编码格式 `类型-长-宽-高-舞台宽-舞台深-配置-…`（以 `-` 分隔），段数可变，缺失段取 0。
- 测试：每个任务先写 pytest 失败测试，再实现，再跑通，再 commit。测试不依赖网络和真实 LLM。
- 目录规范：引擎代码放 `app/engines/<name>/`，规则数据放 `app/engines/<name>/rules.py`（导入时写入 DB），测试放 `tests/unit/test_engine_<name>.py`。
- 不修改现有 Product 表结构；新增字段走新表。
- commit message 前缀：`feat(engine-xxx):`。

## File Structure

新增/修改文件一览：

```
app/engines/
  __init__.py                  # 引擎注册与统一入口 list_engines()
  deviation/
    __init__.py
    matcher.py                 # 字符评分匹配核心（移植 VBA 算法 + 双字加权）
    llm_enhance.py             # 可选 LLM 语义评分（无 key 时自动降级）
    model.py                   # 数据类：TenderItem, ProductCandidate, MatchResult
    rules.py                   # 评分权重配置（可写库）
  meeting/
    __init__.py
    codec.py                   # 编码字符串解析/生成（jiexi 移植）
    selector.py                # 选型主逻辑（解释器规则 → 完成表行）
    rules.py                   # 选型规则表定义 + 初始种子数据
  broadcast/
    __init__.py
    calculator.py              # 点位→功率→功放选型
    rules.py                   # 喇叭功率表、功放功率档位
  led/
    __init__.py
    layout.py                  # 意向尺寸→箱体/模组排布→分辨率/功耗
    rules.py                   # 屏体规格表种子
app/db/
  models.py                    # 修改：新增引擎相关表
  migrate.py                   # 修改：确保新表创建
app/generators/
  excel_generator.py           # 修改：新增 build_meeting_list / build_broadcast_list / build_led_list / build_deviation_sheet 增强
app/api/
  routes_generate.py           # 修改：暴露 4 个生成端点
tests/unit/
  test_engine_deviation.py     # 新增
  test_engine_meeting.py       # 新增
  test_engine_broadcast.py     # 新增
  test_engine_led.py           # 新增
  test_excel_builders.py       # 新增（4 个 Excel 构建器）
```

## 阶段总览

| 阶段 | 内容 | 对应工具 | 产出 |
|---|---|---|---|
| P0 | 数据模型扩展 | 全部 | 新表 + 迁移 |
| P1 | 偏离表引擎 | 偏离表工具 | matcher + LLM 增强 + Excel |
| P2 | 会议选型引擎 | 会议清单工具 | codec + selector + Excel |
| P3 | 广播计算引擎 | 广播清单工具 | calculator + Excel |
| P4 | LED 排布引擎 | LED 工具 | layout + Excel |
| P5 | API 接线 + 文档 | 全部 | 4 个端点 + 使用说明 |


---

## P1：偏离表引擎

### Task 1.1: 字符评分匹配核心（matcher）

**Files:**
- Create: `app/engines/deviation/model.py`, `app/engines/deviation/matcher.py`
- Test: `tests/unit/test_engine_deviation.py`

**Interfaces:**
- `TenderItem(requirement: str)` — 招标单条参数
- `ProductCandidate(model: str, params: list[str])` — 投标产品及参数列表
- `MatchResult(model, matched_param, score, confidence)` — confidence ∈ {high, medium, low}
- `match_tender_to_product(tender_items: list[str], candidates: list[ProductCandidate], rules: dict | None = None) -> list[MatchResult]`
  - 规则默认取 DEFAULT_DEVIATION_RULES
  - 逐字拆分 tender_item，对候选产品的每个参数计分：
    - 单字命中：数字 +numeric_char_weight(0.2)，否则 +single_char_weight(0.75)
    - 双字命中：数字 +numeric_double_weight(0.75)，否则 +double_char_weight(1.0)
  - 取总分最高参数；最高分 0 → matched_param=""，confidence="low"
  - confidence：score>=6 high；2<=score<6 medium；0<score<2 low

- [ ] **Step 1: 写失败测试**

```python
def test_match_simple_keyword():
    cand = ProductCandidate("DS-8004", ["支持输入输出支持HDMI1.4", "双向串口控制"])
    results = match_tender_to_product(
        ["1、支持≥4个HDMI输入接口", "2、支持双向串口控制"], [cand])
    assert len(results) == 2
    assert results[1].matched_param == "双向串口控制"
    assert results[1].confidence == "high"

def test_match_no_hit_returns_low():
    cand = ProductCandidate("X-1", ["完全无关的参数A"])
    r = match_tender_to_product(["激光投影技术参数"], [cand])[0]
    assert r.matched_param == "" and r.confidence == "low"

def test_numeric_chars_score_lower():
    cand = ProductCandidate("Y-2", ["支持4路输入"])
    r = match_tender_to_product(["支持4路输入"], [cand])[0]
    assert r.confidence == "high"
```

- [ ] **Step 2: 跑测试确认失败** → FAIL
- [ ] **Step 3: 实现 model.py**

```python
from dataclasses import dataclass, field

@dataclass
class TenderItem:
    requirement: str

@dataclass
class ProductCandidate:
    model: str
    params: list[str] = field(default_factory=list)

@dataclass
class MatchResult:
    model: str
    matched_param: str
    score: float
    confidence: str
```

- [ ] **Step 4: 实现 matcher.py**

```python
from app.engines.deviation.model import ProductCandidate, MatchResult
from app.engines.deviation.rules import DEFAULT_DEVIATION_RULES

def _is_num(ch: str) -> bool:
    return ch.isdigit() or ch in ".%≥≤"

def _score_pair(tender: str, param: str, rules: dict) -> float:
    score = 0.0
    for i in range(len(tender)):
        c = tender[i]
        if c in param:
            score += rules["numeric_char_weight"] if _is_num(c) else rules["single_char_weight"]
            if i + 1 < len(tender) and tender[i:i+2] in param:
                score += rules["numeric_double_weight"] if _is_num(c) else rules["double_char_weight"]
    return score

def match_tender_to_product(tender_items, candidates, rules=None):
    rules = rules or dict(DEFAULT_DEVIATION_RULES)
    out = []
    for item in tender_items:
        best_score, best_param, best_model = 0.0, "", ""
        for cand in candidates:
            for p in cand.params:
                s = _score_pair(item, p, rules)
                if s > best_score:
                    best_score, best_param, best_model = s, p, cand.model
        if best_score == 0:
            out.append(MatchResult("", "", 0.0, "low"))
        elif best_score >= 6:
            out.append(MatchResult(best_model, best_param, best_score, "high"))
        elif best_score >= 2:
            out.append(MatchResult(best_model, best_param, best_score, "medium"))
        else:
            out.append(MatchResult(best_model, best_param, best_score, "low"))
    return out
```

- [ ] **Step 5: 跑测试通过** → PASS
- [ ] **Step 6: 提交** `git commit -am "feat(engine-deviation): char-score matcher core"`


### Task 1.2: 从产品库构建候选（DB 接线）

**Files:**
- Create: `app/engines/deviation/db_bridge.py`
- Test: `tests/unit/test_engine_deviation.py`

**Interfaces:**
- `build_candidates_from_db(session, models: list[str]) -> list[ProductCandidate]`
  - 对每个 model 查 products 表；description 按 `1.`/`2.` 或换行拆分为参数列表
  - 查不到的产品跳过

- [ ] **Step 1: 写失败测试**

```python
def test_build_candidates_from_db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="矩阵", model="DS-8004",
                      description="1.支持HDMI1.4\n2.双向串口控制"))
        s.commit()
        cands = build_candidates_from_db(s, ["DS-8004"])
        assert len(cands) == 1 and cands[0].model == "DS-8004"
        assert len(cands[0].params) == 2
```

- [ ] **Step 2: 确认失败 → Step 3: 实现**

```python
import re
from app.db.models import Product
from app.engines.deviation.model import ProductCandidate

def _split_params(desc: str) -> list[str]:
    parts = re.split(r"\n|(?=\d+[.、])", desc or "")
    return [p.strip() for p in parts if p.strip()]

def build_candidates_from_db(session, models):
    out = []
    for m in models:
        p = session.query(Product).filter_by(model=m).first()
        if p:
            out.append(ProductCandidate(model=m, params=_split_params(p.description)))
    return out
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-deviation): db candidate bridge"`


### Task 1.3: LLM 语义增强（可选降级）

**Files:**
- Create: `app/engines/deviation/llm_enhance.py`
- Test: `tests/unit/test_engine_deviation.py`

**Interfaces:**
- `enhance_with_llm(results, tender_items, llm_enabled=True, session=None) -> list[MatchResult]`
  - llm_enabled=False → 原样返回（不抛异常）
  - 对 medium/low 且非空的匹配调用 LLM 判断，返回新 confidence
  - 测试 monkeypatch `_llm_judge`，不依赖网络

- [ ] **Step 1: 写失败测试**

```python
def test_llm_enhance_disabled_returns_original(monkeypatch):
    r = MatchResult("M", "p", 3.0, "medium")
    out = enhance_with_llm([r], ["招标参数"], llm_enabled=False)
    assert out == [r]

def test_llm_enhance_upgrades_confidence(monkeypatch):
    monkeypatch.setattr("app.engines.deviation.llm_enhance._llm_judge",
                        lambda *a, **k: ("high", "理由"))
    r = MatchResult("M", "p", 3.0, "medium")
    out = enhance_with_llm([r], ["招标参数"], llm_enabled=True)
    assert out[0].confidence == "high"
```

- [ ] **Step 2: 确认失败 → Step 3: 实现**

```python
def _llm_judge(tender, matched_param):
    # 默认实现调用 app.llm 的 provider；测试中 monkeypatch 替换
    raise NotImplementedError

def enhance_with_llm(results, tender_items, llm_enabled=True, session=None):
    if not llm_enabled:
        return results
    try:
        out = []
        for i, r in enumerate(results):
            if r.confidence in ("medium", "low") and r.matched_param:
                conf, _ = _llm_judge(tender_items[i], r.matched_param)
                if conf in ("high", "medium", "low"):
                    r.confidence = conf
            out.append(r)
        return out
    except Exception:
        return results  # 任何异常降级为原结果
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-deviation): optional llm enhance with fallback"`


### Task 1.4: 偏离表 Excel 构建器

**Files:**
- Modify: `app/generators/excel_generator.py`
- Test: `tests/unit/test_excel_builders.py`

**Interfaces:**
- `build_deviation_sheet(out_path, header: dict, rows: list[dict], template_path=None) -> str`
  - rows: `[{seq, device, tender_param, bid_model, bid_param, deviation, note}]`
  - 列：序号 | 货物名称 | 招标文件要求 | 投标文件实际情况 | 响应情况 | 说明
  - 无 template_path 新建表并写表头，有则加载模板填充

- [ ] **Step 1: 写失败测试**

```python
def test_build_deviation_sheet(tmp_path):
    out = tmp_path / "deviation.xlsx"
    path = build_deviation_sheet(str(out), {}, [
        {"device": "矩阵", "tender_param": "1、≥4路HDMI", "bid_model": "DS-8004",
         "bid_param": "1.支持HDMI1.4", "deviation": "无偏离", "note": ""},
    ])
    wb = load_workbook(path)
    ws = wb.active
    assert ws.cell(1, 2).value == "货物名称"
    assert ws.cell(2, 2).value == "矩阵"
```

- [ ] **Step 2: 确认失败 → Step 3: 实现**

```python
def build_deviation_sheet(out_path, header, rows, template_path=None):
    wb = Workbook() if not template_path else load_workbook(template_path)
    ws = wb.active
    if not template_path:
        ws.append(["序号", "货物名称", "招标文件要求", "投标文件实际情况", "响应情况", "说明"])
    for i, r in enumerate(rows, start=1):
        ws.append([r.get("seq", i), r.get("device", ""), r.get("tender_param", ""),
                   r.get("bid_param", ""), r.get("deviation", ""), r.get("note", "")])
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-deviation): excel builder"`


---

## P2：会议选型引擎

### Task 2.1: 编码解析器（codec）

**Files:**
- Create: `app/engines/meeting/codec.py`
- Test: `tests/unit/test_engine_meeting.py`

**Interfaces:**
- `parse_code(code: str) -> MeetingParams`
- `MeetingParams(scene, length_m, width_m, height_m, stage_w, stage_d, config, extra)`，`area` 为属性 = length*width
- 段序（移植自 itc）：`jiexi(0)=长,1=宽,2=高,3=舞台宽,4=舞台深,5=会议室类型,6=音响配置,7=特殊音响配置,8=话筒配置,9=天线`
- scene 映射：1=圆桌, 2=阶梯, 3=报告厅；未知→圆桌
- config 映射：1=高配, 2=中配, 3=低配；未知→中配

- [ ] **Step 1: 写失败测试**

```python
def test_parse_code_full():
    p = parse_code("12-10-4-0-0-1-2-0-1-0-")
    assert p.scene == "圆桌"
    assert p.length_m == 10 and p.width_m == 4
    assert p.config == "中配"
    assert p.area == 40

def test_parse_code_missing_segments():
    p = parse_code("10-4-")
    assert p.height_m == 0 and p.config == "中配" and p.area == 40

def test_parse_code_bad_scene_falls_back():
    p = parse_code("99-5-5-")
    assert p.scene == "圆桌"
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

```python
from dataclasses import dataclass, field

SCENE_MAP = {"1": "圆桌", "2": "阶梯", "3": "报告厅"}
CONFIG_MAP = {"1": "高配", "2": "中配", "3": "低配"}

@dataclass
class MeetingParams:
    scene: str = "圆桌"
    length_m: float = 0
    width_m: float = 0
    height_m: float = 0
    stage_w: float = 0
    stage_d: float = 0
    config: str = "中配"
    extra: dict = field(default_factory=dict)

    @property
    def area(self) -> float:
        return self.length_m * self.width_m

def _seg(parts, i, default="0"):
    return parts[i] if i < len(parts) and parts[i] else default

def parse_code(code: str) -> MeetingParams:
    parts = code.split("-")
    p = MeetingParams(
        scene=SCENE_MAP.get(_seg(parts, 5), "圆桌"),
        length_m=float(_seg(parts, 0) or 0),
        width_m=float(_seg(parts, 1) or 0),
        height_m=float(_seg(parts, 2) or 0),
        stage_w=float(_seg(parts, 3) or 0),
        stage_d=float(_seg(parts, 4) or 0),
        config=CONFIG_MAP.get(_seg(parts, 6), "中配"),
    )
    p.extra = {"音响配置": _seg(parts, 6), "特殊音响配置": _seg(parts, 7),
               "话筒配置": _seg(parts, 8), "天线": _seg(parts, 9)}
    return p
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-meeting): codec parser"`


### Task 2.2: 选型规则种子（rules）

**Files:**
- Create: `app/engines/meeting/rules.py`
- Test: `tests/unit/test_engine_meeting.py`

**Interfaces:**
- `seed_selection_rules(session) -> None`（幂等，重复调用不重复插入）
- 初始规则 3 组场景 × 5 角色 = 15 条（主音箱/功放/处理器/调音台/显示）
- 型号映射到产品库真实存在值：圆桌 MH-VS08/MH-L240/MH-MA0808/MH-V5-MIX1004/EG65MZ；阶梯 MH-VS10/EG75MZ；报告厅 MH-VS12/MH-L440/MH-MA1616/MH-V5-MIX1812/EG86MZ（实施时以 `app/engines/meeting/rules.py` 为准）

- [ ] **Step 1: 写失败测试**

```python
def test_seed_selection_rules(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_selection_rules(s)
        seed_selection_rules(s)  # 幂等
        n = s.query(SelectionRule).count()
        assert n >= 15
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现 rules.py**

```python
from app.db.models import SelectionRule

_INIT = [
    ("圆桌", 0, 9999, "中配", "主音箱", "MH-VS08", 2, "只"),
    ("圆桌", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("圆桌", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("圆桌", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("圆桌", 0, 9999, "中配", "显示", "EG65MZ", 1, "台"),
    ("阶梯", 0, 9999, "中配", "主音箱", "MH-VS10", 4, "只"),
    ("阶梯", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("阶梯", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("阶梯", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("阶梯", 0, 9999, "中配", "显示", "EG75MZ", 1, "台"),
    ("报告厅", 0, 9999, "中配", "主音箱", "MH-VS12", 4, "只"),
    ("报告厅", 0, 9999, "中配", "功放", "MH-L440", 1, "台"),
    ("报告厅", 0, 9999, "中配", "处理器", "MH-MA1616", 1, "台"),
    ("报告厅", 0, 9999, "中配", "调音台", "MH-V5-MIX1812", 1, "台"),
    ("报告厅", 0, 9999, "中配", "显示", "EG86MZ", 2, "台"),
]

def seed_selection_rules(session):
    for (scene, amin, amax, lvl, role, model, qty, unit) in _INIT:
        exists = session.query(SelectionRule).filter_by(
            scene=scene, config_level=lvl, device_role=role, model=model).first()
        if not exists:
            session.add(SelectionRule(scene=scene, area_min=amin, area_max=amax,
                                      config_level=lvl, device_role=role,
                                      model=model, qty=qty, unit=unit))
    session.commit()
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-meeting): selection rule seeds"`

### Task 2.3: 选型主逻辑（selector）

**Files:**
- Create: `app/engines/meeting/selector.py`
- Test: `tests/unit/test_engine_meeting.py`

**Interfaces:**
- `select_devices(session, params: MeetingParams) -> list[dict]`
  - 按 params.scene + config_level 从 selection_rules 查规则，过滤 area 区间
  - 每行补产品信息：join products 表取 name/规格(description 首行)/品牌/型号/单位；价格留空
  - 返回 `[{seq, name, spec, brand, model, qty, unit, price: 0}]`

- [ ] **Step 1: 写失败测试**

```python
def test_select_devices_meeting(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="8寸多功能专业音箱", model="MH-VS08", brand="MAXHUB",
                      description="8寸两分频无源音箱"))
        s.add(Product(name="2*400W数字功放", model="MH-L240", brand="MAXHUB",
                      description="双通道数字功放"))
        s.commit()
        seed_selection_rules(s)
        rows = select_devices(s, parse_code("1-10-5-"))
        assert len(rows) >= 5
        tk = [r for r in rows if r["model"] == "MH-VS08"][0]
        assert tk["name"] == "8寸多功能专业音箱" and tk["qty"] == 2
        assert tk["price"] == 0
```


- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现 selector.py**

```python
from app.db.models import Product, SelectionRule
from app.engines.meeting.codec import MeetingParams

def select_devices(session, params: MeetingParams) -> list[dict]:
    rules = (session.query(SelectionRule)
             .filter_by(scene=params.scene, config_level=params.config)
             .filter(SelectionRule.area_min <= params.area,
                     SelectionRule.area_max >= params.area)
             .all())
    rows = []
    for i, r in enumerate(rules, start=1):
        prod = session.query(Product).filter_by(model=r.model).first()
        rows.append({
            "seq": i,
            "name": prod.name if prod else r.model,
            "spec": (prod.description.split("\n")[0] if prod and prod.description else ""),
            "brand": prod.brand if prod else "itc",
            "model": r.model,
            "qty": r.qty,
            "unit": r.unit,
            "price": 0,
        })
    return rows
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-meeting): selector"`

### Task 2.4: 会议清单 Excel 构建器

**Files:**
- Modify: `app/generators/excel_generator.py`
- Test: `tests/unit/test_excel_builders.py`

**Interfaces:**
- `build_meeting_list(out_path, header: dict, rows: list[dict], template_path=None) -> str`
  - 表头行：项目名称/报价日期/项目公司/报价单位（header 可选）
  - 数据列：序号 | 产品名称 | 产品规格 | 品牌 | 产品型号 | 数量 | 单位 | 单价 | 总价 | 备注

- [ ] **Step 1: 写失败测试**

```python
def test_build_meeting_list(tmp_path):
    out = tmp_path / "meeting.xlsx"
    path = build_meeting_list(str(out), {"项目名称": "测试会议室"}, [
        {"name": "8寸多功能专业音箱", "spec": "8寸", "brand": "MAXHUB", "model": "MH-VS08",
         "qty": 2, "unit": "只", "price": 0},
    ])
    wb = load_workbook(path)
    ws = wb.active
    assert ws.cell(1, 2).value == "项目名称"
    assert ws.cell(3, 2).value == "全频音箱"
    assert ws.cell(3, 5).value == "MH-VS08"
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

```python
def build_meeting_list(out_path, header, rows, template_path=None):
    wb = Workbook() if not template_path else load_workbook(template_path)
    ws = wb.active
    ws.append(["", "项目名称", header.get("项目名称", ""), "", "报价日期", header.get("报价日期", "")])
    ws.append(["", "项目公司", header.get("项目公司", ""), "", "报价单位", header.get("报价单位", "")])
    ws.append(["序号", "产品名称", "产品规格", "品牌", "产品型号", "数量", "单位", "单价", "总价", "备注"])
    for i, r in enumerate(rows, start=1):
        ws.append([i, r.get("name", ""), r.get("spec", ""), r.get("brand", ""),
                   r.get("model", ""), r.get("qty", 1), r.get("unit", "台"),
                   r.get("price", 0), r.get("total", 0), r.get("note", "")])
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-meeting): excel builder"`


---

## P3：广播计算引擎

### Task 3.1: 喇叭规格种子 + 点位功率计算

**Files:**
- Create: `app/engines/broadcast/rules.py`, `app/engines/broadcast/calculator.py`
- Test: `tests/unit/test_engine_broadcast.py`

**Interfaces:**
- `seed_speaker_specs(session) -> None`（幂等）
- `compute_zone_power(zone: dict[str, int], specs: dict[str, float]) -> float`，返回 `sum(qty*power)`
- `select_amplifier(power_w: float, tiers: list[AmplifierTier]) -> str`，按 min_w < power_w <= max_w 匹配，无匹配返回 ""

- [ ] **Step 1: 写失败测试**

```python
def test_compute_zone_power():
    specs = {"T-105": 6.0, "T-601": 10.0}
    assert compute_zone_power({"T-105": 12, "T-601": 4}, specs) == 112

def test_select_amplifier():
    tiers = [AmplifierTier(min_w=0, max_w=60, model="T-60"),
             AmplifierTier(min_w=60, max_w=120, model="T-120")]
    assert select_amplifier(80, tiers) == "T-120"
    assert select_amplifier(500, tiers) == ""

def test_seed_speaker_specs(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_speaker_specs(s)
        assert s.query(SpeakerSpec).count() >= 8
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现 rules.py**

```python
from app.db.models import SpeakerSpec

_SPEAKERS = [
    ("T-105", 6, "天花喇叭"), ("T-601", 10, "壁挂喇叭"),
    ("T-701A", 10, "壁挂音柱"), ("T-802", 25, "防水音柱"),
    ("T-803", 35, "防水音柱"), ("T-804", 45, "防水音柱"),
    ("T-904", 120, "大功率防水音柱"), ("T-300", 15, "草地音响"),
]

def seed_speaker_specs(session):
    for model, w, cat in _SPEAKERS:
        if not session.query(SpeakerSpec).filter_by(model=model).first():
            session.add(SpeakerSpec(model=model, power_w=w, category=cat))
    session.commit()
```

- [ ] **Step 4: 实现 calculator.py**

```python
def compute_zone_power(zone, specs):
    return sum(qty * specs.get(model, 0) for model, qty in zone.items())

def select_amplifier(power_w, tiers):
    for t in sorted(tiers, key=lambda x: x.max_w):
        if t.min_w < power_w <= t.max_w:
            return t.model
    return ""
```

- [ ] **Step 5: 测试通过 → Step 6: 提交** `git commit -am "feat(engine-broadcast): speaker specs and power calc"`


### Task 3.2: 广播清单 Excel 构建器

**Files:**
- Modify: `app/generators/excel_generator.py`
- Test: `tests/unit/test_excel_builders.py`

**Interfaces:**
- `build_broadcast_list(out_path, header, zones: list[dict], rows: list[dict], template_path=None) -> str`
  - zones: `[{zone, T-601: 12, power_w, amplifier}]`
  - rows: 清单行 `[{seq, name, model, qty, unit, note}]`

- [ ] **Step 1: 写失败测试**

```python
def test_build_broadcast_list(tmp_path):
    out = tmp_path / "broadcast.xlsx"
    path = build_broadcast_list(str(out), {}, [
        {"zone": "分区1", "T-601": 12, "power_w": 180, "amplifier": "T-240"}],
        [{"name": "壁挂喇叭", "model": "T-601", "qty": 12, "unit": "只"}])
    wb = load_workbook(path)
    ws = wb.active
    assert ws.cell(2, 2).value == "分区1"
    assert ws.cell(2, 5).value == "T-240"
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

```python
def build_broadcast_list(out_path, header, zones, rows, template_path=None):
    wb = Workbook() if not template_path else load_workbook(template_path)
    ws = wb.active
    ws.append(["公共广播系统点位汇总"])
    ws.append(["分区", "喇叭明细", "总功率(W)", "选用功放"])
    for z in zones:
        detail = " ".join(f"{k}x{v}" for k, v in z.items()
                          if k not in ("zone", "power_w", "amplifier"))
        ws.append([z.get("zone", ""), detail, z.get("power_w", 0), z.get("amplifier", "")])
    ws.append([])
    ws.append(["序号", "产品名称", "产品型号", "数量", "单位", "备注"])
    for i, r in enumerate(rows, start=1):
        ws.append([i, r.get("name", ""), r.get("model", ""),
                   r.get("qty", 1), r.get("unit", "只"), r.get("note", "")])
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-broadcast): excel builder"`


---

## P4：LED 排布引擎

### Task 4.1: 屏体规格种子 + 排布计算

**Files:**
- Create: `app/engines/led/rules.py`, `app/engines/led/layout.py`
- Test: `tests/unit/test_engine_led.py`

**Interfaces:**
- `seed_led_specs(session) -> None`（幂等，从逆向的 LED 规格表取常见室内屏）
- `calc_layout(want_w_m: float, want_h_m: float, panel: LedPanelSpec, round_mode: str = "就近") -> dict`
  - 返回 `{count_w, count_h, actual_w_m, actual_h_m, res_w, res_h, total_pixels_wan, power_kw, cable_mm2}`
  - count_w = round(want_w_m*1000 / module_w_mm)（round_mode=就近）；`向上`→ceil，`向下`→floor
  - power_kw = actual_w*actual_h*panel_power_per_m2*1.3（panel 增加字段 power_per_m2，默认 300W/m²）
  - cable_mm2 = round(power_kw*1000/38 / 1) 取整向上（38A 载流近似）

- [ ] **Step 1: 写失败测试**

```python
def test_calc_layout_round_mode():
    panel = LedPanelSpec(model="TV-PH250-YZ", module_w_mm=250, module_h_mm=250,
                         res_w=64, res_h=64, type="常规室内屏")
    r = calc_layout(6, 4, panel, "就近")
    assert r["count_w"] == 24 and r["count_h"] == 16
    assert abs(r["actual_w_m"] - 6.0) < 1e-6
    assert r["res_w"] == 24 * 64 and r["res_h"] == 16 * 64

def test_calc_layout_ceil_floor():
    panel = LedPanelSpec(model="P2", module_w_mm=320, module_h_mm=160,
                         res_w=160, res_h=80, type="常规室内屏")
    assert calc_layout(5, 3, panel, "向上")["count_w"] == 16
    assert calc_layout(5, 3, panel, "向下")["count_w"] == 15
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现 rules.py**

```python
import math
from app.db.models import LedPanelSpec

_PANELS = [  # 逆向自 itc 常见屏/规格表（模组 mm, 分辨率）
    ("TV-PH250-YZ", 250, 250, 64, 64, "常规室内屏", 300),
    ("TV-PH200-YZ", 200, 200, 80, 80, "常规室内屏", 350),
    ("TV-PH150-YZ", 150, 150, 106, 106, "常规室内屏", 400),
    ("TV-PH100-YZ", 100, 100, 160, 160, "常规室内屏", 450),
]

def seed_led_specs(session):
    for model, mw, mh, rw, rh, typ, power in _PANELS:
        if not session.query(LedPanelSpec).filter_by(model=model).first():
            session.add(LedPanelSpec(model=model, module_w_mm=mw, module_h_mm=mh,
                                     res_w=rw, res_h=rh, type=typ))
    session.commit()
```


- [ ] **Step 4: 实现 layout.py**

```python
import math
from app.db.models import LedPanelSpec

_POWER_PER_M2_DEFAULT = 300  # W/m²

def _count(want_mm: float, module_mm: float, mode: str) -> int:
    if mode == "向上":
        return math.ceil(want_mm / module_mm)
    if mode == "向下":
        return math.floor(want_mm / module_mm)
    return round(want_mm / module_mm)

def calc_layout(want_w_m, want_h_m, panel: LedPanelSpec,
                round_mode="就近", power_per_m2=None):
    power_per_m2 = power_per_m2 or _POWER_PER_M2_DEFAULT
    cw = _count(want_w_m * 1000, panel.module_w_mm, round_mode)
    ch = _count(want_h_m * 1000, panel.module_h_mm, round_mode)
    aw = cw * panel.module_w_mm / 1000
    ah = ch * panel.module_h_mm / 1000
    res_w = cw * panel.res_w
    res_h = ch * panel.res_h
    power_kw = aw * ah * power_per_m2 * 1.3 / 1000
    cable_mm2 = math.ceil(power_kw * 1000 / 38)
    return {
        "count_w": cw, "count_h": ch,
        "actual_w_m": aw, "actual_h_m": ah,
        "res_w": res_w, "res_h": res_h,
        "total_pixels_wan": res_w * res_h / 10000,
        "power_kw": round(power_kw, 2),
        "cable_mm2": cable_mm2,
    }
```

- [ ] **Step 5: 测试通过 → Step 6: 提交** `git commit -am "feat(engine-led): panel specs and layout calc"`

### Task 4.2: LED 清单 Excel 构建器

**Files:**
- Modify: `app/generators/excel_generator.py`
- Test: `tests/unit/test_excel_builders.py`

**Interfaces:**
- `build_led_list(out_path, header: dict, layout: dict, rows: list[dict], template_path=None) -> str`
  - 第一段：意向/实际尺寸与分辨率、功耗、电缆；第二段：设备清单行

- [ ] **Step 1: 写失败测试**

```python
def test_build_led_list(tmp_path):
    out = tmp_path / "led.xlsx"
    layout = {"count_w": 24, "count_h": 16, "actual_w_m": 6.0, "actual_h_m": 4.0,
              "res_w": 1536, "res_h": 1024, "power_kw": 9.36, "cable_mm2": 247}
    path = build_led_list(str(out), {"项目名称": "LED屏"}, layout,
                          [{"name": "模组", "model": "TV-PH250-YZ", "qty": 384, "unit": "块"}])
    wb = load_workbook(path)
    ws = wb.active
    assert ws.cell(1, 2).value == "6.0m × 4.0m"
    assert ws.cell(3, 2).value == "TV-PH250-YZ"
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现**

```python
def build_led_list(out_path, header, layout, rows, template_path=None):
    wb = Workbook() if not template_path else load_workbook(template_path)
    ws = wb.active
    ws.append(["屏体尺寸", f"{layout.get('actual_w_m', 0)}m × {layout.get('actual_h_m', 0)}m"])
    ws.append(["分辨率", f"{layout.get('res_w', 0)} × {layout.get('res_h', 0)}"])
    ws.append(["序号", "产品名称", "产品型号", "数量", "单位", "备注"])
    for i, r in enumerate(rows, start=1):
        ws.append([i, r.get("name", ""), r.get("model", ""),
                   r.get("qty", 1), r.get("unit", "块"), r.get("note", "")])
    ws.append([])
    ws.append(["总功耗(KW)", layout.get("power_kw", 0), "电缆线径(mm²)", layout.get("cable_mm2", 0)])
    wb.save(out_path)
    return out_path
```

- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(engine-led): excel builder"`


---

## P5：API 接线 + 集成冒烟 + 文档

### Task 5.1: 四个生成端点

**Files:**
- Modify: `app/api/routes_generate.py`
- Test: `tests/unit/test_excel_builders.py` 仅新增 smoke（API 层用 FastAPI TestClient）

**Interfaces:**
- `POST /api/engines/deviation` body `{tender_items, models, llm_enabled}` → `{file, results, low_confidence}`
- `POST /api/engines/meeting` body `{code, header}` → `{file, rows}`
- `POST /api/engines/broadcast` body `{zones, header}` → `{file, zones_with_power, rows}`
- `POST /api/engines/led` body `{want_w_m, want_h_m, model, round_mode, header}` → `{file, layout, rows}`
- 输出写入 `settings.OUTPUT_DIR/engines/`；无 LLM 时 deviation 自动降级不报错

- [ ] **Step 1: 写失败测试**

```python
def test_engine_meeting_endpoint(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from app.main import app
    r = TestClient(app).post("/api/engines/meeting", json={"code": "1-10-5-", "header": {}})
    assert r.status_code == 200
    data = r.json()
    assert "file" in data and len(data["rows"]) >= 5
```

- [ ] **Step 2: 确认失败**
- [ ] **Step 3: 实现 deviation 端点**（追加到 routes_generate.py，复用 require_token 与 db session）

```python
class EngineDeviationIn(BaseModel):
    tender_items: list[str]
    models: list[str] = []
    llm_enabled: bool = False

@router.post("/engines/deviation")
def engine_deviation(body: EngineDeviationIn):
    from app.db.session import get_session, get_engine
    from app.engines.deviation.matcher import match_tender_to_product
    from app.engines.deviation.db_bridge import build_candidates_from_db
    from app.engines.deviation.llm_enhance import enhance_with_llm
    from app.generators.excel_generator import build_deviation_sheet
    from app.config import settings
    with get_session(get_engine()) as s:
        cands = build_candidates_from_db(s, body.models)
    results = match_tender_to_product(body.tender_items, cands)
    results = enhance_with_llm(results, body.tender_items, llm_enabled=body.llm_enabled)
    os.makedirs(f"{settings.OUTPUT_DIR}/engines", exist_ok=True)
    out = f"{settings.OUTPUT_DIR}/engines/deviation.xlsx"
    rows = [{"device": "", "tender_param": t, "bid_param": r.matched_param,
             "deviation": "" if r.confidence != "low" else "待人工确认",
             "note": r.confidence} for t, r in zip(body.tender_items, results)]
    build_deviation_sheet(out, {}, rows)
    low = sum(1 for r in results if r.confidence == "low")
    return {"file": out, "results": [vars(r) for r in results], "low_confidence": low}
```

- [ ] **Step 4: 其余 3 个端点按同模式实现**（meeting/broadcast/led，签名见各 Task Interfaces，种子规则在端点首次调用时自动 seed）
- [ ] **Step 5: 测试通过 → Step 6: 提交** `git commit -am "feat(api): engine generate endpoints"`


### Task 5.2: 集成冒烟测试 + 文档

**Files:**
- Create: `tests/e2e/test_engines_smoke.py`
- Modify: `docs/使用说明书.md`（新增「方案工具引擎」章节）、`docs/功能说明书.md`

- [ ] **Step 1: 写冒烟测试**（tmp 输出目录，四引擎依次生成断言文件非空）
- [ ] **Step 2: 确认失败 → Step 3: 接线排错 → Step 4: 测试通过**
- [ ] **Step 5: 文档**：使用说明书新增四段（输入/输出/示例编码）；功能说明书登记 4 引擎能力
- [ ] **Step 6: 提交** `git commit -am "docs: engine usage and smoke tests"`

---

## 附录 A：itc 工具包逆向结论（2025-09-03）

- 来源：`/sdcard/Download/数据库/偏离表工具/方案制作工具包/`，4 xlsm + wps.vba.exe（WPS VBA 组件，NSIS 安装包）
- 宏提取：oletools.olevba → `itc_tools/vba/*.vba.txt`
- 会议清单：编码段序 0长/1宽/2高/3舞台宽/4舞台深/5类型/6音响配置/7特殊/8话筒/9天线；类型 1圆桌/2阶梯/3报告厅；配置 1高配/2中配/3低配；输出会议系统设备报价清单
- 广播清单：喇叭功率 T-105:6W T-601:10W T-701A:10W T-802:25W T-803:35W T-804:45W T-904:120W T-300:15W；分区总功率×1.5 选功放
- LED：意向尺寸→模组数取整（就近/向上/向下）→分辨率/功耗（×1.3）/电缆（÷38A）；改单=复制→删"删除项"→重排
- 偏离表：逐字拆分×候选参数模糊计分（单字数字0.2/汉字0.75，双字数字0.75/汉字1.0）取最高分；本方案新增 LLM 语义修正降级通道

---

**（方案完）**

## P0：数据模型扩展

### Task 0.1: 引擎相关新表

**Files:**
- Modify: `app/db/models.py`, `app/db/migrate.py`
- Test: `tests/unit/test_engine_models.py`（新增，校验新表可建、可写读）

**Interfaces:**（SQLAlchemy 2.0 风格，与现有 Base 一致）

```python
class SelectionRule(Base):
    __tablename__ = "selection_rules"
    id, scene(str), area_min(float), area_max(float), config_level(str),
    device_role(str), model(str), qty(int), unit(str), updated_at

class SpeakerSpec(Base):
    __tablename__ = "speaker_specs"
    id, model(str, unique), power_w(float), category(str)

class LedPanelSpec(Base):
    __tablename__ = "led_panel_specs"
    id, model(str, unique), module_w_mm(int), module_h_mm(int),
    res_w(int), res_h(int), type(str)

class AmplifierTier(Base):
    __tablename__ = "amplifier_tiers"
    id, min_w(float), max_w(float), model(str)
```

- [ ] **Step 1: 写失败测试**：用 get_engine(sqlite tmp) + Base.metadata.create_all 建表，插入/查询 4 张新表各一条，断言成功
- [ ] **Step 2: 确认失败**（ImportError: 无 SelectionRule）→ **Step 3: 实现**：models.py 加 4 个类；main.py 已自动 create_all，migrate 无需额外 DDL（新表由 create_all 创建）
- [ ] **Step 4: 测试通过 → Step 5: 提交** `git commit -am "feat(db): engine tables (selection rules, speaker/led specs, amp tiers)"`


### 执行补充：面积分档（2025-09-04）

会议引擎种子升级为面积分档：主音箱/功放按会议室面积三档（0-150 / 150-250 / 250+ 平）自动升级，
对应业务口径「100平 / 200平 / 300平成套方案」：

- 圆桌中配：80平→MH-VS08×2，170平→MH-VS10×4，286平→MH-VS12×6；功放固定 MH-L240。
- 阶梯/报告厅按同口径分档（MH-VS10→VS12、PAS15），高配报告厅功放 MH-V5-PA2100×2。
- 话筒段（1=手持/2=无线会议/3=数字会议）与天线段（仅配无线话筒）保持三场景通用。
- seed 幂等升级：旧 0-9999 主音箱规则按 (scene, config, role) 命中分档时清理，其余保留；
  话筒/天线规则含 mic/ant 约束的旧行就地补字段。
- 测试：新增 `test_area_tiers_change_speaker_qty`（80/170/286 平三档断言 + 功放唯一性），
  配置梯度断言同步面积档口径（120平高配 VS10×2、低配 VS06×2）。
