# Spec: 招标文件改单引擎（Tender Re-Match）

日期：2026-09-05 · 版本：v1.0.5 目标功能 · 状态：已批准（用户确认方案 v2 + 品牌自适应 + 匹配策略参数化）

## 1. Objective

用户上传招标参数文件（docx / xlsx，含设备清单与参数），系统按**应标品牌**在本地产品库中做**就近参数匹配**，结合**架构拓扑映射**判断集成合并、能力缺口与冗余，输出可直接编辑的 BOM（复用现有 BOM 编辑器），每行带状态徽标与备注（新增/集成/冗余原因），确认后重出 Excel。

用户故事：
- 招标 4 只 150W/8Ω 音箱 + 1 台四通道功放，应标品牌惠威只有 80W/180W 与双通道功放 → 音箱就近取 180W；功放新增至 2 台双通道，备注写明「惠威无四通道，双通道×2 替代」
- 招标广播系统列「广播主机 / 前置放大器 / 调谐器 / USB播放器」，惠威某型号已集成调谐器+USB → 只填该型号，冗余行标红，备注「该型号已集成…满足需求」
- 用户新增厂商（思必驰/迪士普/ITC）产品入库存后，零代码改动即可用该品牌改单（品牌自适应）

## 2. 核心原则

- **品牌无关**：品牌池 = `products.brand DISTINCT` 动态发现；匹配/能力/拓扑逻辑不写死任何品牌词表
- **就近匹配**：默认 higher（就近取高规格）；用户声明性价比/价格无优势 → value 模式（就近取低 + 差价超阈值降级提示）
- **LLM 可降级**：识别/能力标注/建议型号均可在无 key 或失败时退化为纯规则结果

## 3. 数据模型

### 3.1 产品能力标签（新表 `product_capabilities`）
id, product_id, capability(能力码), source('rule'|'llm'), confidence, updated_at
能力码枚举（可扩展，前缀系统）：tuner 调谐器, usb_player, preamp 前置放大, mixer, dsp, amp_2ch/amp_4ch 功放通道, display 显示, touch, camera, mic, array_mic, processor 处理器, relay, matrix_hdmi, hdmi_in/out ...
生成策略：导入/入库时由 capability_tagger 规则推断（名称+描述+role_tags 关键词映射），新产品品牌首次出现时可选 LLM 精修后缓存。

### 3.2 匹配快照（新表 `tender_match`）
project_id, source_row(原文行号), brand(招标), model(招标型号), qty, params_json,
matched_product_id, matched_model, score, status(matched|partial|no_match|merged|extra|new),
remark(备注), preference(higher|value), snapshot_time
冗余行 extra 与合并行 merged 用 merged_into 记录集成目标。

### 3.3 行状态
| status | 含义 | 展示 |
|---|---|---|
| matched | 就近命中库内产品 | 绿，备注选型依据 |
| partial | 品牌/型号命中但参数有差异 | 黄，待确认 |
| no_match | 库内无候选（品牌缺失等） | 新增，备注原因 |
| merged | 功能被其他产品集成 | 标红，备注集成说明 |
| extra | 冗余（用户可删，以用户操作为准） | 标红 |

## 4. 组件与数据流

tender_parser（docx/xlsx -> TenderItem[]）
  -> tender_matcher（品牌过滤 -> 能力覆盖 -> 参数维度就近）
       -> architecture_mapper（角色分组 -> 集成合并 -> 拓扑计算 -> 完整性校验）
            -> llm_pick（模糊识别/能力精修/新增建议，可降级）
                 -> tender_store（快照持久化）-> API -> BOM 编辑器 -> rebuild Excel

### 4.1 tender_parser
- docx：python-docx 遍历表格 + 段落；xlsx：openpyxl 多 sheet（复用 product_importer 表头定位思路）
- 表头识别：品牌/型号/名称/数量/参数列定位；多行参数合并（续行、单元格内换行）
- 输出 TenderItem{idx, brand, model, name, qty, params[], raw}

### 4.2 参数维度提取器（dimensions.py）
- 通用「数值+单位」模式：数字+(W|Ω|欧|Hz|kHz|dB|英寸|寸|CH|通道|路|m|mm) + 已知维度正则表
- 输出 DimMap{dim: (value, unit, raw)}，如 {power: 150, impedance: 8, freq_hz: (60,20000), sens_db: 90}
- 距离度量：同维数值归一化 |a-b|/max；频响按上下界差；维度权重表可配置
- 维度表可扩展（新增维度只需加正则条目，不改匹配逻辑）

### 4.3 tender_matcher（就近匹配）
1. 品牌硬约束：招标 brand 非空 -> 候选池 = 该品牌产品；库内无该品牌 -> no_match（新增）
2. 型号精确/包含匹配（model 字段）-> 命中即 matched
3. 否则能力覆盖评分（capability 匹配）-> 覆盖最高者入围
4. 参数维度就近：多候选按 DimMap 距离排序取最近；同距离/模糊 -> 按 preference 决策：
   - higher（默认）：取高规格；备注「就近取高：招标 X -> 候选 Y」
   - value：取低规格；若高规格差价 > 阈值（默认 15%，可配）-> 备注「价格无优势，取低」
5. 返回 MatchResult{product, score, dims_gap, remark}

### 4.4 architecture_mapper（架构映射）
1. 招标项按 role（tagger 复用：名称/型号 -> role_code）分组
2. 组内集成判定：候选产品 capabilities 覆盖多项招标需求并集 -> 合并，被合并项 status=merged + merged_into，备注集成说明
3. 拓扑计算：数量关系映射（例：音箱 N 只 + 功放 M 台通道数 C -> 库内通道数 c'，所需台数 = ceil(N / c')；若 > 招标台数 -> 新增差额台数，备注公式）
4. 完整性校验：按 system × role 模板查缺：系统必需角色缺失 -> 补充项 status=no_match(新增)，备注「架构补充」
5. 冗余判定：合并后未被任何需求覆盖的招标项 -> extra 标红

### 4.5 llm_pick（LLM 增强，全部可降级）
- 模糊行识别：参数/名称无法规则归一的设备行
- capability 精修：新品牌首导入时补能力标签
- 新增项建议型号：no_match 行给出建议型号（备注「建议：XXX」）
- 复用 app.llm.prompts 风格，temperature=0，JSON 解析失败即降级

## 5. API

- POST /api/projects/{id}/tender-match：multipart（file + brand 可选 + preference 可选）-> SSE 进度（parse -> match -> architecture -> llm）-> 完成返回匹配快照（行列表）
- GET /api/projects/{id}/tender-match：读取最近快照
- 确认后走现有 POST /api/projects/{id}/rebuild 重出 Excel（BOM 行含 status/remark 透传）

## 6. 前端

- 项目文件页新增「招标改单」按钮 -> 抽屉：上传文件 + 应标品牌下拉（品牌池动态）+ 匹配策略切换（性能优先/性价比优先）
- 结果载入 BOM 编辑器：每行状态徽标 + 备注列显示原因；标红行可一键删除（用户指定为准）
- 复用进度条（SSE 四步）

## 7. 测试策略

- 单元：维度提取（150W/8Ω/频响/灵敏度/通道数）、就近匹配（higher/value/差价降级）、集成合并（调谐器+USB）、拓扑（四通道→双通道×2）、品牌缺失→新增、LLM 降级
- 解析：docx/xlsx 夹具（表格+多行参数+多 sheet）
- e2e：上传→快照→BOM 载入→rebuild 链路
- 回归：全量 pytest 保持全绿

## 8. 实施顺序

1. 数据模型 + capability_tagger + dimensions 提取器（含测试）
2. tender_parser（docx/xlsx 夹具测试）
3. tender_matcher + architecture_mapper + llm_pick（降级路径测试）
4. API + SSE + 快照持久化
5. 前端按钮/抽屉/状态徽标/删除交互
6. rebuild 透传 + e2e + 全量回归 -> 发布 v1.0.5

## 9. 边界

- 库内无应标品牌 -> 全部判新增并备注，不伪造匹配
- 用户删除标红行 -> 以用户操作为准，不自动删
- 新增行价格留空标「待询价」（沿用现有规则）
- 不修改招标文件本体；快照仅存项目库
