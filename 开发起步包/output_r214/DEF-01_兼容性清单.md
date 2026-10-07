# DEF-01 统一全站 403 信封——兼容性清单与选定契约（214 批次A E-A2）

> 裁决：用户 2026-10-06 已选 A（统一信封），非改断言（212 B07 口径）。
> 本文先盘点两套 403 的全部生产方与消费方，再写定契约；实施与回归按 §5。

## 1. 生产方盘点（后端）

### 1.1 main.py 认证中间件（`auth_and_logging_middleware`，已近信封形）

| 位置 | 触发 | 现状响应体 | 与契约差距 |
|---|---|---|---|
| main.py:644 | API Key 校验失败（`_check_token`：无效或已禁用 / 已过期，main.py:445/448） | `{"code":403,"message":err,"data":None}` | 缺 `request_id`、缺 `detail` 镜像 |
| main.py:653 | RBAC 粗门禁 `_enforce_rbac`：`权限不足：Token 未绑定用户角色` / `权限不足` / `权限不足：写操作需要绑定角色`（main.py:539/542/558） | `{"code":403,"message":rbac_err,"data":None,"request_id"}` | 缺 `detail` 镜像 |

### 1.2 core/security.py `require_permission`（DEF-01 漂移根源）

- security.py:59 `raise HTTPException(status_code=403, detail=f"缺少权限: {resource_code}")` → FastAPI 默认渲染 **`{"detail":"缺少权限: xxx"}`**，与全局 `{code,message,data}` 信封漂移。
- 调用方（37 个文件，均为端点依赖注入，读 detail 字段的是 FastAPI 序列化器）：
  admin.py、ai.py、ai_accuracy.py、ai_quality.py、candidates.py、data_products.py、datasets.py、dict_general_api.py、dict_medical_api.py、dict_medical_import_api.py、dict_medical_push_api.py、governance.py、governance_ops.py、graph.py、identity.py、identity_sync.py、lineage.py、metadata_changes.py、metrics.py、ops_tools.py、permission_requests.py、permissions.py、probe.py、quality.py、quality_controls.py、quality_issues.py、quality_notifications.py、quality_observations.py、quality_runs.py、quality_vendors.py、queries.py、recipes.py、relation_reviews.py、relations.py、systems.py、tables.py、value_domains.py
- 附带：security.py:21 `get_current_user` 403 `Token 未绑定可信操作人`；security.py:87 `require_query_view_on_get` 复用 require_permission（同源）。

### 1.3 其它直接 `HTTPException(403)`（同样走 FastAPI 默认 `{"detail"}`，一并统一形状）

| 文件:行 | detail |
|---|---|
| core/auth.py:33 | 无效或已禁用的 API Token |
| api/v1/auth.py:103 | CSRF 校验失败 |
| api/v1/auth.py:168 | 权限不足 |
| api/v1/quality_observations.py:98/101/104 | 无权查看（三态，含 quality.issue.read_all 提示） |
| api/v1/quality_runs.py:172 | 仅运行管理员或发起者可取消 |
| api/v1/ai_accuracy.py:168 | 缺少权限: feedback:create 或 feedback:review |
| api/v1/ai_accuracy.py:183 | str(exc)（AI 工具拒绝） |
| api/v1/governance_ops.py:42/336 | 常驻调度需 platform_admin / 变体 |
| api/v1/permission_requests.py:206 | grant_role_forbidden: 仅平台管理员… |
| services/dict_sync_executor.py:539/660 | infectious sync 执行器未注册 / 需独立审批 |
| services/medical_code_push.py:883/1079/1483/1487/1492/1511 | 下发链路权限族 |
| api/v1/datasets.py:80/109/222/244/270/477 | 数据集业务规则拒绝（撤销/同人约束族） |

## 2. 消费方盘点（前端）

| 消费方 | 读取字段 | 统一后行为 | 需适配 |
|---|---|---|---|
| utils/errorMessage.ts `extractErrorDetail`（146 D1 中央提取器） | `detail → message → error_summary_masked → error.message` | `detail` 镜像保留 → 优先命中旧文案，显示不变 | 否 |
| views 内 detail-only 读取（systems/index.vue:156/175/189、table-detail:533、dict/general:362、dict/medical/OverviewPanel:50、identity/accounts:250、local-accounts:195/273、departments:182、persons:204、permission-requests:163、asset/overview:225 等） | `detail \|\| 兜底文案` | `detail` 镜像保留 → 兼容；无 detail 的 403 走兜底文案 | 否 |
| relation-recipes/index.vue:72、login/index.vue:117-119 | `detail \|\| message \|\| …` | 两字段链均兼容 | 否 |
| utils/http/index.ts 拦截器 | 不读业务字段（透传 response.data） | 不受影响 | 否 |

结论：**前端零代码改动**——契约在信封里保留 `detail` 兼容镜像（DEF-09 房式），中央提取器与全部 detail-only 读取方行为不变。

## 3. 消费方盘点（测试）

- `tests/test_dict_medical.py::test_asset_viewer_cannot_read_medical_code_sets`（209 的 DEF-01 失败项）：断言 `message=="权限不足"` ×2 —— 统一后**自然转绿**，断言不改。
- 其余 detail 断言（17 个文件）经扫描均为 400/404/409/422 等非 403 路径（"403 + detail" 组合 0 处）；全库无 403 响应体整字典比较 → 不受影响。
- `tests/plan194/test_def09_envelope.py`：401/423/429 已用 `{code,message,data,detail}` 信封 → 403 统一沿用同形，无冲突。

## 4. 选定契约（本清单即合同）

**全站 403 统一信封**（沿用 DEF-09 房式 `{code,message,data,detail}`，补 `request_id`）：

```json
{
  "code": 403,
  "message": "权限不足",
  "data": { "resource_code": "dict.medical.view" },
  "detail": "缺少权限: dict.medical.view",
  "request_id": "32位hex"
}
```

- **message**：权限拒绝族统一 `权限不足`；中间件既有带说明变体（Token 未绑定用户角色/写操作需要绑定角色/API Token 失效族）保留原文，同为 message 字段。
- **data**：`require_permission` 拒绝时 `{"resource_code": "<权限码>"}`；其余 `null`。
- **detail**：兼容镜像。`require_permission` 场景镜像旧文案 `缺少权限: <权限码>`（老读取方无感）；其余场景 `== message`。
- **request_id**：与 111 S6 关联 ID 同源；中间件 L644 一并补齐。
- 非字符串 detail（未来防御）：message 落 `权限不足`，detail 落 JSON 串。
- HTTPException 携带的 headers（如 WWW-Authenticate）原样保留。
- **仅 403 重塑**；401/404/409/422 等保持既有形状（401 中间件本就是 {code,message}、429 走 DEF-09 handler）。

## 5. 实施与回归

1. `core/security.py`：新增 `PermissionDenied(HTTPException)`（detail=`权限不足`，携 `resource_code` 与 `legacy_detail`）；`require_permission` 改抛它。
2. `main.py`：注册 `HTTPException` 处理器——403 按上文契约重塑，非 403 委托 FastAPI 默认 `http_exception_handler`；中间件 L644 补 `request_id`+`detail`，L653 补 `detail`。
3. 契约固定：新增 `tests/test_forbidden_envelope_214.py`（纯逻辑直调 handler + TestClient 端到端断言四件套+镜像+resource_code）。
4. 回归：`tests/test_dict_medical.py` 全文件转绿（不改其断言）→ 受影响套件 → 全量 pytest。
