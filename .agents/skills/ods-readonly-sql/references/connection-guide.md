# 数据中心 ODS 只读连接指南

## 已登记连接身份

| 项目 | 当前值 |
|---|---|
| 平台系统编码 | `DATA_CENTER` |
| 平台数据源编码 | `ods_8_216` |
| 数据库类型 | Oracle 11g |
| 服务名 | `orcl` |
| 凭据引用 | `file:///etc/data-asset/credentials/ods_8_216` 或 `env:CRED_ODS_8_216` |
| 写策略 | `readonly` |

地址和端口由平台连接记录或 `APP_ODS_HOST`、`APP_ODS_PORT` 提供。AI 应优先读取平台连接配置，不要把地址、账号或密码抄入 SQL、提示词或报告。

## 运行位置选择

### A. Windows 仓库本机

本机不能直连业务库，使用仓库 `OracleConnector` 的 `ssh_jump` 模式：

```powershell
cd F:\python\数据资产\backend

$env:APP_ODS_CONNECTION_MODE = 'ssh_jump'
$env:APP_SSH_JUMP_HOST = '10.10.8.53'
$env:APP_SSH_JUMP_PORT = '40022'
$env:APP_SSH_JUMP_USER = 'dataasset'
$env:APP_SSH_JUMP_KEY = 'F:\python\数据资产\.ssh\id_ed25519_ai'
$env:APP_SSH_KNOWN_HOSTS = 'F:\python\数据资产\.ssh\known_hosts'
$env:APP_ORACLE_CLIENT_LIB_DIR = '/opt/oracle/instantclient_21'

# 认证信息必须由安全渠道注入；不要把真实值写进脚本或聊天记录。
$env:CRED_ODS_8_216 = '<readonly-user>:<readonly-password>'

python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py --test-connection
```

SSH 使用 `BatchMode=yes` 和严格 known_hosts。连接失败时不得改成自动接受主机指纹。

### B. 生产服务器应用容器/内网运行环境

内网环境使用 direct：

```powershell
$env:APP_ODS_CONNECTION_MODE = 'direct'
$env:APP_ORACLE_CLIENT_LIB_DIR = '/opt/oracle'
$env:APP_ODS_CREDENTIAL_FILE = '/etc/data-asset/credentials/ods_8_216'

python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py --test-connection
```

如果技能脚本在宿主机仓库而 Python 依赖只存在于容器，应从当前发布目录把脚本作为只读工具运行在应用容器内；不要复制凭据到临时目录，也不要输出凭据文件内容。

普通查询通过 `--max-rows` 控制，范围为 `1–10000`。文件导出通过 `--export-file` 和 `--export-max-rows`，上限为 `50000`；导出只支持 direct 模式，不能通过旧跳板模式传输五万行结果。

### C. 平台 API

优先流程：

1. `POST /api/v1/ai/sessions` 创建会话；
2. `GET /api/v1/ai/system-context?system_code=DATA_CENTER&max_tables=30`；
3. `POST /api/v1/ai/export-context` 核对字段和关系；
4. `POST /api/v1/ai/sql-risk-scan`；
5. `POST /api/v1/ai/propose-sql` 保存草稿；
6. 人工批准后调用 `POST /api/v1/ai/drafts/{draft_id}/execute`，请求中使用 `source_code=ods_8_216`；当前平台 API 契约上限为 `max_rows<=5000`。需要10000行查询或50000行文件导出时，改用服务器内网 direct 执行器，不擅自绕过 API 契约。

接口需要合法 Token 和权限。Token 不写入 Skill 或命令历史，使用调用工具的安全认证配置。

## 支持的认证变量

按优先级：

1. `APP_ODS_USER` + `APP_ODS_PASSWORD`；
2. `CRED_ODS_8_216=user:password`；
3. 兼容变量 `CRED_ODS=user:password`；
4. `APP_ODS_CREDENTIAL_FILE` 指向受控文件，默认 `/etc/data-asset/credentials/ods_8_216`。

不得使用命令行 `--password`，不得从仓库历史脚本中复制默认口令。

## 查询参数文件

SQL 使用 Oracle 绑定变量，例如 `:start_time`。参数文件是 JSON 对象：

```json
{
  "start_time": "2026-07-01 00:00:00",
  "end_time": "2026-07-02 00:00:00"
}
```

日期值能否由驱动按目标字段类型直接转换必须在限量验证时确认；必要时在 SQL 中使用明确且一致的 `TO_DATE(:start_time, 'YYYY-MM-DD HH24:MI:SS')`，不要依赖会话隐式日期格式。

## 连接成功判定

- `--test-connection` 返回 `ok=true`；
- 只执行 `SELECT 1 AS OK FROM dual`；
- 日志不出现凭据；
- 未执行任何 DDL/DML；
- 正式查询仍需通过静态门禁并限制行数。

## 查询与导出上限

| 模式 | 上限 | 输出 | 限制 |
|---|---:|---|---|
| 平台 API 查询 | 5000行 | API 脱敏样本 | 服从当前 OpenAPI 契约 |
| Skill 普通查询 | 10000行 | 标准输出 JSON | `--max-rows<=10000` |
| Skill 文件导出 | 50000行 | CSV或JSONL | 仅 direct；仓库外路径；敏感列遮蔽 |

导出示例：

```powershell
New-Item -ItemType Directory -Force D:\exports | Out-Null
python ..\.agents\skills\ods-readonly-sql\scripts\run_ods_readonly.py `
  --sql-file D:\temp\ods_query.sql `
  --params-file D:\temp\ods_params.json `
  --export-file D:\exports\ods_result.csv `
  --export-format csv `
  --export-max-rows 50000
```

导出完成只报告文件路径、行数和是否可能截断，不把五万行内容直接发送到 AI 对话。
