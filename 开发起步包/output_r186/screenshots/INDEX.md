# output_r186 截图索引（tools/capture_186_screens.py，本地新构建 + 确定性 API fixture）

> 采集环境：vite preview（本地 dist，r186 构建）+ 请求拦截 fixture（真实 DTO 形状；未触生产）。
> 验收账号：fixture platform_admin（permissions=["*:*:*"]）。
> 尺寸：默认 1366×768；03 为 1920×1080；10 为 1024 宽。

| 文件 | 内容 | 验证点 |
|---|---|---|
| 01_登录页_静态无动态路由.png | 登录页 | N3：整轮捕获 0 次 get-async-routes 请求（browser_requests_static_mode.json） |
| 02_工作台_1366.png | 工作台+七分区菜单 | W1 四卡 + 菜单 4/5/7/6/3/9/6 |
| 03_工作台_1920.png | 工作台 1920 | U1 尺寸 |
| 04_资产目录_系统与数据资源.png | systems 页 | 分区入口 |
| 05_标准与关系_值域.png | 值域知识库 | 分区入口 |
| 06_质量治理_台账.png | 质量台账 | 分区入口 + scope |
| 07_查询与指标_运行记录直达.png | /asset/queries?tab=runs | Q1 页签直达恢复 |
| 08_人员与权限_同步日志_账号状态.png | 同步日志 + 账号启停状态表 | I1/I3 §4.6.5 字段（在职/HIS人员/HIS账号/期望/嘉和/无纸化/观察时间） |
| 09_平台运维_治理配置_页签.png | /asset/admin?tab=tokens | O1 页签化（tokens/owners/terms/snapshots） |
| 10_工作台_1024可用.png | 工作台 1024 宽 | U1 窄屏可用 |

fixture 数据均为合成示例（工号脱敏形态），非生产数据。
