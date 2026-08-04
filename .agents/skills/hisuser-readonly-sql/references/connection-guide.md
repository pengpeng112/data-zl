# HIS_SOURCE 只读连接指南

## 已登记连接身份

| 项目 | 当前值 |
|---|---|
| 平台系统编码 | `HIS_SOURCE` |
| 当前数据源编码 | `his_source_10_10_10_15` |
| 数据库类型 | Oracle 11g |
| 服务名 | `his` |
| 凭据文件 | `/etc/data-asset/credentials/his_source_10_10_10_15` |
| 写策略 | `readonly` |

地址、端口和用户名优先从平台连接记录或环境变量读取。不要把连接账号当成 Schema；业务表仍使用真实 Owner。

## A. Windows 工作站：登记别名连接 data-asset-83（优先）

配置文件存在时统一使用：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83
```

必须遵守：禁止读取、显示、复制或修改私钥；禁止关闭或绕过 `StrictHostKeyChecking`；禁止把 SSH/数据库密码写进命令、脚本、日志、Skill 或 Git。登录服务器不等于获得写库授权，业务源库仍只允许单条 `SELECT` 或只读 CTE。

标准流程：

1. 用无副作用命令测试 SSH：

   ```powershell
   ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83 "printf CONNECTION_OK"
   ```

2. 确认 `data-asset-api` 容器和只读凭据文件名；只列名称，不读取内容：

   ```powershell
   ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83 `
     "docker ps --format '{{.Names}}'; docker exec data-asset-api ls -1 /etc/data-asset/credentials"
   ```

3. 在容器内使用 `/app/app/services/db_connectors.py` 的 `OracleConnector`、`validate_readonly_sql` 和凭据文件 `/etc/data-asset/credentials/his_source_10_10_10_15`。开启只读事务，超时不超过120秒；普通查询不超过10000行，文件导出不超过50000行。

4. 执行前通过静态只读检查。巨表按业务键和时间范围收窄；年度指标只返回年度和汇总值，不返回患者标识。交付/Excel 中保存带 `--` 中文说明的核查版 SQL，至少解释主要 JOIN、统计时间、业务筛选和排除条件。

   当前 `validate_readonly_sql` 执行门禁不接受注释，因此实际执行前仅机械删除核查版中的注释行或行尾注释，生成临时执行版。禁止在去注释过程中改变任何查询逻辑。可以对去注释后的规范化文本做一致性复核；执行完成后删除临时执行版，不用它覆盖 Excel 中的核查版。

5. 需要传输本地 SQL 时，只传不含凭据的 SQL 和受控执行脚本。临时文件可放服务器及容器 `/tmp`，完成后立即两处清理；不得复制凭据或患者明细到 `/tmp`。

6. 结果报告必须包含 `readonly=true`、`business_source_writes=0`、返回行数和截断状态，不得输出连接串、用户名、密码或原始异常凭据。

7. 回写 Excel 前先备份。SQL 写入指定分子/分母列，统计值按年份写入末尾年度列；保存后重新打开文件核对单元格。

8. 连接失败时停止并报告 SSH 错误类型。不得改用聊天中的明文密码、自动接受未知主机、猜测账号或扫描网络。

## B. Windows 仓库本机：旧 SSH 跳板方式

本机不能直接访问 HIS，使用既有跳板：

```powershell
cd F:\python\数据资产\backend

$env:APP_HIS_SOURCE_CONNECTION_MODE = 'ssh_jump'
$env:APP_SSH_JUMP_HOST = '10.10.8.53'
$env:APP_SSH_JUMP_PORT = '40022'
$env:APP_SSH_JUMP_USER = 'dataasset'
$env:APP_SSH_JUMP_KEY = 'F:\python\数据资产\.ssh\id_ed25519_ai'
$env:APP_SSH_KNOWN_HOSTS = 'F:\python\数据资产\.ssh\known_hosts'
$env:APP_ORACLE_CLIENT_LIB_DIR = '/opt/oracle/instantclient_21'

# 通过安全渠道注入；不要把真实值写进 Skill、脚本或提示词。
$env:APP_HIS_SOURCE_USER = '<readonly-user>'
$env:APP_HIS_SOURCE_PASSWORD = '<readonly-password>'

python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py --test-connection
```

也可以只设置 `CRED_HIS_SOURCE='<readonly-user>:<readonly-password>'`。SSH 强制 known_hosts 校验；不得使用自动接受未知主机。

## C. 生产服务器应用容器/内网环境：直连

```powershell
$env:APP_HIS_SOURCE_CONNECTION_MODE = 'direct'
$env:APP_ORACLE_CLIENT_LIB_DIR = '/opt/oracle'
$env:APP_HIS_CREDENTIAL_FILE = '/etc/data-asset/credentials/his_source_10_10_10_15'

python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py --test-connection
```

如果宿主机没有 backend Python 依赖，应在应用容器内执行当前发布版本的脚本，复用已挂载的只读凭据卷。不要读取、打印或复制凭据内容到 `/tmp`、报告或聊天。

## D. 平台 API

推荐顺序：

1. `POST /api/v1/ai/sessions`；
2. `GET /api/v1/ai/system-context?system_code=HIS_SOURCE&max_tables=30`；
3. `POST /api/v1/ai/export-context`；
4. `POST /api/v1/ai/sql-risk-scan`；
5. `POST /api/v1/ai/propose-sql`；
6. 人工批准后调用 `POST /api/v1/ai/drafts/{draft_id}/execute`，使用 `source_code=his_source_10_10_10_15`；当前平台 API 契约上限为 `max_rows<=5000`。需要10000行查询或50000行导出时使用服务器内网 direct 执行器。

Token 由客户端安全认证配置注入，不写命令、Skill 或报告。

## 支持的环境变量

| 变量 | 用途 |
|---|---|
| `APP_HIS_SOURCE_HOST` | 目标地址；通常由平台配置提供 |
| `APP_HIS_SOURCE_PORT` | Oracle 端口 |
| `APP_HIS_SOURCE_SERVICE` | 服务名，当前为 `his` |
| `APP_HIS_SOURCE_USER` / `APP_HIS_SOURCE_PASSWORD` | 分离凭据 |
| `CRED_HIS_SOURCE` | `user:password` 组合凭据 |
| `APP_HIS_CREDENTIAL_FILE` | 受控凭据文件路径 |
| `APP_HIS_SOURCE_CONNECTION_MODE` | `direct` 或 `ssh_jump` |
| `APP_ORACLE_CLIENT_LIB_DIR` | Oracle Client thick 路径 |
| `APP_HIS_QUERY_TIMEOUT_MS` | 1000–120000 毫秒 |
| `APP_SSH_JUMP_*` | 跳板地址、端口、用户、密钥、known_hosts |

## 限量查询示例

`D:\temp\his_query.sql`：

```sql
SELECT
    pv.PATIENT_ID,
    pv.VISIT_ID
FROM MEDREC.PAT_VISIT pv
WHERE pv.PATIENT_ID = :patient_id
  AND pv.VISIT_ID = :visit_id
```

`D:\temp\his_params.json`：

```json
{
  "patient_id": "由调用方安全提供",
  "visit_id": 1
}
```

执行：

```powershell
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py `
  --sql-file D:\temp\his_query.sql `
  --params-file D:\temp\his_params.json `
  --max-rows 100
```

参数文件可能包含患者标识，只能放在 Git 忽略的临时目录，使用后安全清理；不得提交仓库或附在报告中。

## 成功判定

- 连接测试只执行 `SELECT 1 AS OK FROM dual`；
- 查询执行前通过仓库只读门禁；
- Oracle 会话执行 `SET TRANSACTION READ ONLY`；
- 普通查询不超过10000行，文件导出不超过50000行，并进行敏感列遮蔽；
- 业务源库写入为0。

## 查询与导出上限

| 模式 | 上限 | 输出 | 限制 |
|---|---:|---|---|
| 平台 API 查询 | 5000行 | API 脱敏样本 | 服从当前 OpenAPI 契约 |
| Skill 普通查询 | 10000行 | 标准输出 JSON | `--max-rows<=10000` |
| Skill 文件导出 | 50000行 | CSV或JSONL | 仅服务器内网 direct；仓库外路径；敏感列遮蔽 |

导出示例：

```powershell
New-Item -ItemType Directory -Force D:\exports | Out-Null
python ..\.agents\skills\hisuser-readonly-sql\scripts\run_his_readonly.py `
  --sql-file D:\temp\his_query.sql `
  --params-file D:\temp\his_params.json `
  --export-file D:\exports\his_result.csv `
  --export-format csv `
  --export-max-rows 50000
```

导出完成只报告文件路径、行数和是否可能截断；不要将五万行数据直接输出到聊天或日志。
