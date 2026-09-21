# r194 隔离证据（194 §2.3-6 运行期断言）

- 断言方式：后端请求日志全文 grep（logs/backend.log，覆盖 20:55–22:00 全部流量）
- `10\.10\.|10\.255\.|dify|hospital_llm|smtp` 命中数 = **0**（真实源库/Dify/LLM/邮件出口调用 0 次）
- `APScheduler started|scheduler started` 命中数 = **0**（调度未启动；asset_scheduler_jobs scheduled 行=0，四个功能开关全 false）
- 写执行器：asset_action_executors 全程 0 行；O03 用例证明未注册执行器 404
- 启动日志仅 `Identity nightly sync is disabled (APP_IDENTITY_NIGHTLY_ENABLED=false)` 一条降级提示
- 测试写入全部落在 data_asset_test（会话内二次核实 current_database()）与一次性库 data_asset_test_r194（迁移专项，已保留待清理）
- 本机 SSH 仅用于仓库标准测试隧道（tools/dev_env.sh → 15432），未执行生产 HTTP/容器/平台写操作
- 429 限流两次命中（登录 5/min）——属平台自身行为，非外部调用
