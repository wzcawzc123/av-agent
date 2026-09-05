# 功能缺口补全待办（审计于 2026-09-05）

> 来源：三份并行审计（前端-后端 API 对照 / README-功能说明书声明核对 / 架构级剩余缺口）。
> 结论：v3.0 架构（Planner/Agents/Workflow/企业表/知识库/记忆）与招标、BOM、提供商体系均真实接线、非空壳；
> 但存在 **6 类功能性断线、13 处前端错误处理缺陷、1 批文档过期**，另有打包验证未完成。以下全部为待办。

## A. 功能性断线（后端）

- [ ] **A1 招标鉴权体系不匹配**：`static/tender.js` 用 `Authorization: Bearer` + `localStorage["token"]`，后端只认 `X-Access-Token`（`app/api/deps.py`），局域网（README 主打的手机控制电脑场景）下招标改单全部 401。
  方案：`require_token` 同时兼容 `X-Access-Token` 与 `Authorization: Bearer`；前端统一改 `X-Access-Token`。
- [ ] **A2 招标 project_id 硬编码 "1"**：`tender.js:17` 写死 `project_id=1`，`index.html:62` 显示写死，与聊天选择的项目无联动，多项目数据串号。
  方案：从 app.js 当前项目状态读取（`window.__projectId`），展示同步更新。
- [ ] **A3 招标「确认改单」是空操作**：`routes_tender.py` confirm 只 `to_bom_rows` 返回 JSON，不写 `Project.bom_json`、不落表、不生成 Excel，前端 alert 行数后丢弃。
  方案：确认时写 `Project.bom_json` + 生成设计方案 Excel（复用 `build_design_sheet`），返回 `{bom, excel_path}`。
- [ ] **A4 配置模板闭环断裂**：`compose_devices(config_template)` 形参从未使用；`adapt.py` 唯一消费方无调用；模板能存能匹配但内容不加载进新项目 BOM（「同类项目直接复用」承诺不成立）。
  方案：compose_devices 把 `config_template.config_json["rows"]` 作主设备基底，缺失角色用 `SYSTEM_BUILDERS` 补全后照常 backfill。
- [ ] **A5 PPT 模板工作流失效**：`solution_design` 的 `find_doc_template` 结果写局部 `tpl_paths` 从不回写 `context.cfg["template_paths"]`，且不按 doc/ppt 类型区分（类型串扰）。
  方案：`find_doc_template` 加 type 参数按 doc_type 过滤；solution_design 写回 cfg；document_generation 从 cfg 取 ppt/deviation 模板。
- [ ] **A6 偏离表交付物为占位**：document_generation 与 pipeline 写死单行「满足」，无真实比对内容。
  方案：优先取该项目最近招标快照（`engines/tender/store.py` + `TenderMatch` matched/partial 行）做偏离行；无招标数据回退占位。
- [ ] **A7 偏离表模板无上传入口**：`routes_data.py` 上传只允许 doc/ppt。
  方案：放开 `doc_type=deviation`（xlsx）。
- [ ] **A8 Redis 声明未接线**：`AV_REDIS_URL` 只读环境变量，全 app 无 redis 客户端；任务队列纯内存，多进程不共享。
  方案：queue.py 检测 REDIS_URL，设置时用 redis.asyncio（惰性 import，ImportError 回退内存），未设置时内存实现完全不变（测试零影响）。
- [ ] **A9 任务持久化缺失**：`TaskRecord` 模型是死模型；队列任务内存态，重启即丢、SSE 订阅断裂。
  方案：submit_task 写 TaskRecord，_run 更新 progress/status；get_task miss 时查表；导出 `recover_stale_tasks(engine)` 启动置 failed（main.py 接入）。
- [ ] **A10 对话消息历史缺失**：无 messages 表，只有内存槽位增量，无多轮上下文、刷新即丢。
  方案：新增 `ChatMessage` 表，routes_chat 写入 user/assistant，新增 `GET /api/projects/{pid}/messages` 读取端点；parse_intent 签名不动。
- [ ] **A11 Solution/Quotation 只写不读**：落库正常但无任何读取端点。
  方案：routes_workflow 补方案/报价查询端点。

## B. 前端缺口（static/）

- [ ] **B1 错误处理统一**：13 处假成功/未检查 `r.ok`（generate 422 无限转圈、chat 显示 undefined、from-bom/pe-save/fetch-models/产品上传/模板注册/upd-save/upd-check/bom-as-template/设为当前 假成功、列表加载 5xx 白屏、SSE 无 onerror）。
  方案：加 `api()` helper（检查 r.ok + 统一提示），逐处替换。
- [ ] **B2 运行记录 UI**：`/api/workflow/runs`、`/runs/{id}`、`/runs/{id}/logs` 零前端消费，用户看不到 v3.0 编排过程。
  方案：项目页加「运行记录」面板（status/progress/plan/agent 日志）。
- [ ] **B3 知识库管理 UI**：`/api/knowledge` CRUD 无入口，RAG 数据只能手工插库。
- [ ] **B4 组织与用户管理 UI**：`/api/organizations`、`/api/users` 无入口（可并入设置抽屉）。
- [ ] **B5 模板「套用」按钮**：`GET /api/templates/{id}/bom` 注释称前端载入但无人调用。
- [ ] **B6 提供商「测试连接」按钮**：`POST /api/providers/{id}/test` 后端完整、前端无按钮。
- [ ] **B7 招标快照历史**：`GET /api/tender/{pid}/snapshots` 无前端选择器。
- [ ] **B8 loadUpdateCfg 回显**：函数定义但从不调用，更新配置永不回显。
- [ ] **B9 sw.js 缓存缺 tender.js**：PWA 离线下招标脚本加载失败。
- [ ] **B10 deliverables 默认值不一致**：`routes_generate.py` 默认 `["doc"]`、`routes_workflow.py` 默认 `["excel"]`，统一为继承需求槽位、缺省 `["doc","excel"]`。

## C. 文档过期

- [ ] **C1** `docs/COMPLETE_PLAN.md`：P2 T1/T2/T3 已实现但仍 `[ ]`，测试数过期 → 勾选并补实现位置。
- [ ] **C2** `docs/功能说明书.md`：config_templates 描述（改为多维匹配）、产品列表上限 500→1000、测试用例数、鉴权章节补本机免口令豁免、adapt.py 标注遗留死代码。
- [ ] **C3** `README.md`：Redis 表述按最终实现改准确；核心能力补运行记录/知识库 UI；多租户表述如实（单 token + 模型预留）。

## D. 打包（Windows exe）

- [ ] **D1** `av-agent.spec` hiddenimports 补 `app.planner/app.agents/app.workflow/app.knowledge/app.engines` + `redis/psycopg`；确认 datas 覆盖 static 全部（manifest/sw.js/tender.js/icons）。
- [ ] **D2** 检查 `exe_entry.py` 是否 import 新模块（保证 exe 内 Agent 注册生效）。
- [ ] **D3** 本机（Linux aarch64）pip install pyinstaller 试构建验证 spec 语法与收集逻辑（PyInstaller 不支持交叉编译，产出 Linux 可执行文件作为链路验证；Windows exe 需在 Windows 执行 `build_exe.bat`）。
- [ ] **D4** 出 Windows exe：在 Windows 机器跑 `build_exe.bat`（安装依赖 → PyInstaller 打包 → `dist\AVAgent.exe`），LibreOffice 用于 PDF。

## E. 收尾（主代理）

- [ ] E1 接入 `recover_stale_tasks` 到 `app/main.py` lifespan。
- [ ] E2 Solution/Quotation 查询端点（若未并入 A11）。
- [ ] E3 全量 pytest + 端到端冒烟（聊天/生成/招标/工作流）回归。
- [ ] E4 提交（feat 补齐缺口）+ 视情况 bump 版本/移动 tag。

## 明确不做（如实降级）

- **LLM 流式输出**：4 个 provider + 路由 + 前端打字机，属体验增强非功能断线，未排入本轮。
- **多租户隔离**：单 token 鉴权 + 局域网使用场景下完整登录/租户体系不现实，`org_id` 作为数据模型预留，文档如实声明单租户。
