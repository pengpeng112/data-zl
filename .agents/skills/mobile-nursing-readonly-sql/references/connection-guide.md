# 移动护理只读连接指南

## 已登记身份

| 项目 | 值 |
|---|---|
| 平台系统编码 | `MOBILE_NURSING` |
| 数据库类型 | Oracle 11g |
| 服务名 | `ewell` |
| Owner | `LUNA_MCS_SDSEY` |
| 写策略 | `readonly` |

地址、端口和凭据应从平台连接记录、环境变量或服务器受控凭据文件取得。不得将账号密码写入技能、SQL、提示词、日志或 Git。

## 推荐运行位置

在已打通免密认证的工作站上，先登录平台服务器：

```powershell
ssh -F "F:\python\数据资产\.ssh\config_ai" data-asset-83
```

随后在 `data-asset-api` 容器/同等内网环境运行仓库脚本，使用挂载的受控凭据文件。不得读取或输出凭据文件内容，也不得把患者明细带出容器。

支持的认证变量：

1. `APP_MOBILE_NURSING_USER` + `APP_MOBILE_NURSING_PASSWORD`；
2. `CRED_MOBILE_NURSING=user:password`；
3. `APP_MOBILE_NURSING_CREDENTIAL_FILE` 指向受控文件。

连接参数：

- `APP_MOBILE_NURSING_HOST`
- `APP_MOBILE_NURSING_PORT`（默认 1521）
- `APP_MOBILE_NURSING_SERVICE`（默认 `ewell`）
- `APP_MOBILE_NURSING_CONNECTION_MODE=direct|ssh_jump`
- `APP_ORACLE_CLIENT_LIB_DIR`

只做连通测试：

```powershell
cd F:\python\数据资产\backend
python ..\.agents\skills\mobile-nursing-readonly-sql\scripts\run_mobile_nursing_readonly.py --test-connection
```

普通查询最大 10000 行。CSV/JSONL 导出最大 50000 行，且仅允许 `direct` 模式和仓库外已存在目录：

```powershell
python ..\.agents\skills\mobile-nursing-readonly-sql\scripts\run_mobile_nursing_readonly.py `
  --sql-file D:\temp\mobile_nursing.sql `
  --params-file D:\temp\params.json `
  --export-file D:\exports\mobile_nursing.csv `
  --export-format csv `
  --export-max-rows 50000
```

连接失败时只报告脱敏错误类型；不得扫描网络、猜测凭据、关闭主机校验或转用写账号。
