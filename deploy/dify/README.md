# Dify AI 质控 Workflow（quality-control-v1）

## 搭建与发布

1. 在内网 Dify 新建 Workflow 应用，按 `input.schema.json` 创建 6 个输入变量。
2. 固定节点链为“输入校验 → 模型分析 → JSON 规范化 → Output”，System Prompt 使用 `system-prompt.txt`。
3. 禁止添加数据库、Knowledge Base 明细、HTTP 回调、Code 写库、Agent Tool 或平台写接口节点。
4. Output 必须符合 `output.schema.json`，并原样回显 `request_id`、`input_digest`。
5. 先用 `synthetic-input.json` 验证 JSON 契约，再发布 Workflow；记录 Dify 内的应用版本，但不要把 Key 导出到 DSL、截图或 Git。
6. 若当前 Dify 版本支持稳定、无秘密的 DSL 导出，可将其另存本目录；不支持时以本目录的 Schema、Prompt 和搭建步骤为权威交付。

## 8.83 配置

- 平台默认 `APP_DIFY_QUALITY_ENABLED=false`。
- API Key 只写入宿主机受控凭据文件，权限必须为 `0600`，以只读方式挂载到容器。
- 平台环境仅配置 `file://` 或 `env:` 引用；不得写入数据库、镜像层、前端、日志或 OpenAPI。
- URL 必须为受控 host 的 `/v1` 根，生产 HTTPS 不得关闭证书校验；医院 CA 用只读 CA bundle。

## 分级验收

1. 关闭态：status 正常，create/connection-test 失败关闭，API/HTML 不出现 Key。
2. 合成数据：发送 `synthetic-input.json`，校验 schema、digest、异常 JSON、超时、401、429、5xx、重定向和超大响应。
3. 单条摘要：只选 1 条无 `sample_data/detail` 的真实 finding，确认 input/output digest 和审计。
4. 小批次：最多 10 条同系统、同数据源、同 schema、同表、同规则 finding。
5. 上述全部通过后才可把开关置 true；首版仍只允许人工触发，禁止新增定时推送。

## 回滚

先把 `APP_DIFY_QUALITY_ENABLED` 置为 false 并重建应用容器，再在 Dify 停用/取消发布 Workflow。保留平台任务、结果和治理审计，不删除历史记录；必要时按应用发布清单回滚后端/前端版本。凭据轮换由受控密钥流程完成，不在此目录记录旧值。
