# r173 T1（C 线）前后端契约比对报告

日期：2026-09-01｜工具：`backend/_r173_work/check_api_contract_r173.py` + `check_field_contract_r173.py`（工装按 round-8 #19 放 `_r173_work/`，计划原文 tools/ 位置已被裁决覆盖，偏差见 exceptions.json）｜数据：`openapi.json`（345 路径/393 操作）+ `app_routes.json`（实路由 400 条，含 3 个 include_in_schema=False 真实别名）

## 一、解析覆盖率（round-8 #10 要求报告）

- 全仓 `http.<method>|http.request` 检索（src/**.ts+*.vue，排除 types.ts）：**289 个 occurrence**
- 成功抽取为调用站点：**286（99.0%）**；未抽取 3 个全部为中文注释提及（asset.ts:286、dict.ts:329、ops.ts:137「视图层不再裸 http.request」字样），零真实漏检
- 修正记录：初版解析器对对象字面量泛型（`http.request<{code:number;...}>`）误判为非调用（漏 54 个），修复后达 99.0%——该修正过程证明漏检风险主要来自封装形态变化，已在不确定项提示后续若改封装需重跑本工装

## 二、路径/方法级比对结果

- 前端调用 286 条 → **自动匹配后端实路由 271 条**
- 未自动匹配 15 条，全部人工裁决为可解析（**非漂移**）：
  - 13 条 `${AI_QUALITY_BASE}` 变量前缀（asset.ts:1456-1473，`AI_QUALITY_BASE="/api/v1/quality/ai"`）→ 后端 /api/v1/quality/ai/{status,connection-test,governance-report,preview,jobs,jobs/{id},jobs/{id}/retry,results/{id}/review,results/{id}/attach,patrol/targets,patrol/runs,patrol/run} 逐条核对全部存在
  - `PATCH /api/v1/permission-requests/${id}/${action}`（permissions.ts:149）→ action 仅 approve|reject，后端两条 PATCH 均存在
  - `POST /api/v1/recipes/.../versions/${v}/${action}`（recipes.ts:128）→ action 仅 submit|approve|reject|activate|deprecate，后端五条全部存在
- **路径/方法级真实漂移：0 条**
- 曾疑似漂移并排除：`GET /api/v1/health`（ops.ts:151）openapi 无此路径 → 实为 `include_in_schema=False` 的 Nginx 反代别名（backend/app/api/v1/health.py:39，与 main.py:318 PUBLIC_PREFIXES 一致），运行时存在。教训：契约比对必须以 `app.routes` 实路由表为准（本报告已改用 app_routes.json）

## 三、后端从未被前端引用的操作（信息项，非漂移）

122/393 操作（31%）前端零引用（contract_diff_raw.json `backend_ops_never_referenced`）——含 admin/init、govern 调度、identity-sync 夜间链路等脚本/运维端点，属设计内（API 优先），但其中 UI 域端点（如 dashboard/summary 已被引用）以外的死端点可由主 AI 复核是否有对应未开发页面。

## 四、字段级契约抽样（round-8 #10：抽样≥30 人工核）

- 静态可比对（前后端双方均声明具名结构）：仅 **9 对**——后端广泛使用 `ApiResponse[dict]` 泛型声明（运行时才确定字段），静态字段比对覆盖率低属诚实边界
- 9 对中 1 条 flag：`PATCH /api/v1/quality/findings/{id}` 前端 api 类型 QualityFindingItem 缺后端返回的 6 字段（assigned_to/confirmed_by/error_cnt/error_rate/sample_data/total_cnt）——**定性为非漂移**：views/asset/quality 通过平行类型 `qualityContracts.ts:90-93` 声明并真实消费这些字段（quality/index.vue:510,548）。副作用发现：**同一响应存在两套平行 TS 类型声明**（api 层 QualityFindingItem 与视图层 qualityContracts.ts），属 P3 代码坏味道（漂移温床）
- 其余 ≥21 个采样点转为 S 线运行时交叉核验（live JSON 顶层 data keys vs 前端消费点），见 S 线报告

## 五、结论

C 线四桶之「契约漂移」计数：**0（真实）**；1 条 P3 坏味道（平行类型双声明）；122 条后端未引用操作作信息项。
