# Docare 手术麻醉只读连接指南

## 登记身份

| 项目 | 值 |
|---|---|
| 平台系统编码 | `DOCARE` |
| 数据库类型 | Oracle 11g |
| 服务名 | `docare` |
| 业务 Owner | `MEDSURGERY`、`MEDCOMM`、`MEDICU` |
| 写策略 | `readonly` |

地址、端口和凭据从平台连接记录、环境变量或服务器受控凭据文件读取。不得把账号密码写入技能、SQL、提示词、日志或 Git。

## 推荐连接方式

医院 Windows 工作站使用已经配置的服务器 SSH 别名：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83
```

连接平台服务器后，在 `data-asset-api` 容器或等效内网环境运行受控脚本。凭据通过只读挂载文件注入，不得显示、复制或修改凭据文件。

认证优先级：

1. `APP_DOCARE_USER` + `APP_DOCARE_PASSWORD`
2. `CRED_DOCARE=user:password`
3. `APP_DOCARE_CREDENTIAL_FILE` 指向受控文件，默认 `/etc/data-asset/credentials/docare_10_10_10_68`

连接参数：

- `APP_DOCARE_HOST`
- `APP_DOCARE_PORT`，默认 1521
- `APP_DOCARE_SERVICE`，默认 `docare`
- `APP_DOCARE_CONNECTION_MODE=direct|ssh_jump`
- `APP_ORACLE_CLIENT_LIB_DIR`
- `APP_DOCARE_QUERY_TIMEOUT_MS`

只做连通测试：

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\docare-anesthesia-readonly-sql\scripts\run_docare_readonly.py --test-connection
```

普通查询：

```powershell
python ..\.agents\skills\docare-anesthesia-readonly-sql\scripts\run_docare_readonly.py `
  --sql-file D:\temp\docare.sql `
  --params-file D:\temp\params.json `
  --max-rows 10000
```

文件导出仅允许服务器内网 `direct` 模式，最多 50000 行，路径必须在 Git 仓库外且目录已存在：

```powershell
python ..\.agents\skills\docare-anesthesia-readonly-sql\scripts\run_docare_readonly.py `
  --sql-file D:\temp\docare.sql `
  --params-file D:\temp\params.json `
  --export-file D:\exports\docare.csv `
  --export-format csv `
  --export-max-rows 50000
```

连接失败时只报告脱敏错误；不得扫描网络、猜凭据、关闭 SSH 主机校验或改用写账号。
