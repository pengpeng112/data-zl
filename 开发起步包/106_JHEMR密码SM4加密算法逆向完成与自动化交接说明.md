> 类别：交接说明
> 状态：当前（2026-08-01 创建；JHEMR 密码 SM4 加密算法完整逆向成功，阻断项解除）

# 106 JHEMR 密码 SM4 加密算法逆向完成与自动化交接说明

## 0. 结论先行

**JHEMR 登录密码 `users.user_pwd_sm` 的 SM4 加密算法已完整逆向并通过正向/逆向双重验证。105 号文档记录的核心阻断项（key_id=102 密钥不可得）经核实与登录密码无关，现已解除。**

后续 AI 可直接据此实现 `set_default_password` 自动化，无需再向厂商索取密钥或 API。本文件不含任何可还原真实账号的完整密钥材料；验证用样本仅保留算法证明所需的最小信息。

## 1. 算法（已验证）

```
密钥 key16 = (user_id + date_str + "bjgoodwill").encode('utf-8')[:16]
  其中 date_str = 密码设置当日 DateTime.Today.ToString("yyyyMMdd")
算法：SM4/ECB/PKCS7Padding
明文：密码字符串的 UTF-8 字节
输出：Base64
```

**密钥结构（恰好 16 字节）**：

| 段 | 来源 | 长度 | 示例（占位） |
|---|---|---|---|
| 工号 | `users.user_login_name` 或 `user_id` | 可变 | `XXXXXX` |
| 日期 | 设置当日 `yyyyMMdd` | 8 | `20260802` |
| 固定盐 | 硬编码 `"bjgoodwill"`（嘉和美康英文缩写） | 补足到 16 | `bj` |

当工号为 6 位时，密钥 = 工号(6) + 日期(8) + `bj`(2) = 16 字节。工号长度不同时盐的截取长度相应变化，但总长度恒为 16。

## 2. 验证证据

正向加密与逆向解密均通过（使用受控样本，工号与密文不在此留存）：

- 正向：用还原算法加密已知明文，输出与数据库 `user_pwd_sm` 完全一致
- 逆向：用还原算法解密数据库密文，得到已知明文
- 日期敏感性：同一明文在不同日期加密产生不同密文（20260801/02/03 三组各不相同），印证密钥含日期分量
- 确定性：同一(工号,日期,密码)三元组多次加密结果相同，**无随机前缀**（推翻 105 号"非确定性"的旧判断）

验证脚本：`C:\temp\jhemr_decomp\confirm_key.py`（本地临时，不入 Git）。

## 3. 逆向过程（供后续 AI 复核）

### 3.1 工具链

- dnSpy 命令行版（`D:\工具\dnSpy-net-6.1.8win64\dnSpy.Console.exe`）在 git bash / PowerShell 重定向下因 `Console.OutputEncoding` 硬抛 `IOException`，不可用
- dnSpy GUI（同目录 `dnSpy.exe`）可用，但本次未依赖
- 实际使用 **Python `dnfile` 库（v0.18.0）** 手写 IL 反汇编器，完成全部方法体静态分析
- 反汇编脚本：`C:\temp\jhemr_decomp\analyze_il.py`、`analyze_dll.py`

### 3.2 调用链还原

```
EmrGetEncodingPassword  (JHServicesLib.dll, MethodDef[2366])
  ├─ SQL: "select is_sm from users where USER_LOGIN_NAME=?"
  ├─ is_sm > 1 → 走 SM4 新路径
  │     └─ EncryptPassword (MethodDef[2367])
  │           ├─ dateStr = DateTime.Today.ToString("yyyyMMdd")
  │           ├─ key = String.Concat(userId, dateStr, "bjgoodwill")
  │           └─ Sm4ExternalMethod.EncryptECB(key[:16], plainPwd)
  └─ is_sm <= 1 → 旧字符混淆路径（Caesar +4/-4，与 JHEMRLoginExtend.dll 同源）
```

### 3.3 关键澄清：key_id=102 与登录密码无关

105 号文档曾将 `SM4:102` / `TKeyDetailInfo.plainkey` 列为核心阻断。本次反编译确认：

- `cryptography.svc.TKeyDetailInfo` / `TKeyInfo` / `TKeyResult` 是 **Thrift 风格的密钥服务数据契约**（`__isset` 字段是 Thrift 标志）
- 它们服务于**另一套独立机制**（疑似数据传输层加密或配置解密），**与 `users.user_pwd_sm` 登录密码加密无调用关系**
- 登录密码的 SM4 密钥完全由客户端本地用 `工号+日期+"bjgoodwill"` 拼接生成，**不调用任何远程密钥服务**

### 3.4 Dotfuscator 混淆的处理

`EncryptPassword` 方法体含 Dotfuscator 控制流混淆（垃圾 `ldc.i4` 常量、虚假分支），但其核心数据流（`String.Concat` 三参数 + `EncryptECB` 调用）可读。`EncryptECB` 的 `isHex` 参数在 IL 中看似为 `true`，但实际密钥是 UTF-8 字节直接截取——因为"工号+日期+盐"前 16 字符均为 ASCII，UTF-8 与 ASCII 字节一致，无需 hex 解码。最终密钥形态由正向加密验证确认。

## 4. JHNetSecuritySM.dll 的其他发现（旁证）

| 方法 | 用途 | 备注 |
|---|---|---|
| `EncryptECB/DecryptECB` (MethodDef[58-61]) | SM4 ECB/CBC 通用包装 | 密钥由调用方传入 |
| `Encrypt` (MethodDef[7]) | **SM2** 椭圆曲线加密（非 SM4） | 含 `G`/`ecc_bc_spec`/`KDF`/`sm3hash`，用于非对称场景 |
| `sm4Sbox/sm4Lt/sm4F/sm4_setkey` (MethodDef[45-53]) | SM4 算法原语 | 标准实现 |
| `EncryptSm4ECB` (JHServicesLib MethodDef[2589]) | 通用 SM4 包装，默认密钥 `"admin123!@#$%^&*"` | 配置加密用，非登录密码 |
| `GetConfig` (JHServicesLib MethodDef[2666]) | 解密 TLS 配置，密钥 `"jhservicetls192.168.7.122"` | 配置解密用 |

## 5. 自动化实现要点

在 `backend/app/services/jhemr_identity_adapter.py` 增加：

```python
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT
import base64, datetime

SM4_SALT = "bjgoodwill"

def encode_jhemr_password(user_id: str, plain_pwd: str, date_str: str = None) -> str:
    """生成 JHEMR user_pwd_sm 密文。
    date_str 为 None 时取当日（注意：JHEMR 客户端用本机日期，服务器与客户端时区一致时等价）。
    """
    if date_str is None:
        date_str = datetime.date.today().strftime("%Y%m%d")
    key16 = f"{user_id}{date_str}{SM4_SALT}".encode("utf-8")[:16]
    sm4 = CryptSM4()
    sm4.set_key(key16, SM4_ENCRYPT)
    ct = sm4.crypt_ecb(plain_pwd.encode("utf-8"))  # gmssl 自动加 PKCS7
    return base64.b64encode(ct).decode()
```

注意：
- 密钥含**设置日期**。若同步程序在 UTC 时区的服务器上运行而 JHEMR 客户端用北京时间，跨日零点前后可能有 1 天偏差。生产实现应显式传入 `date_str`，或用 `Asia/Shanghai` 时区取当日。
- 依赖库 `gmssl`（纯 Python，已 `pip install` 于本机；服务器 8.83 容器需补装）。

## 6. 安全约束（沿用）

- 本文件不含完整工号、密码明文或可还原的密文样本
- 验证用的受控样本仅存于本地临时目录 `C:\temp\jhemr_decomp\`，不进入 Git、聊天或普通日志
- HIS/HISUSER 业务源库只读；JHEMR `users.user_pwd_sm` 的写操作仍须走 dry-run + 人工审批
- 夜间批量和多用户 apply 继续保持关闭，直到单账号自动化验证通过

## 7. 后续步骤

1. 在 `jhemr_identity_adapter.py` 实现 `set_default_password(user_id, password='a')` 并补单测
2. 用第二个受控账号交叉验证算法（不同工号、不同日期）
3. 确认服务器容器 `data-asset-api` 的时区与 JHEMR 客户端一致，避免日期偏差
4. 走 dry-run + 审批门禁后，将 JHEMR 密码自动初始化纳入 apply 流程
5. 更新 55 号计划的 JHEMR 阻断项状态

## 8. 关联文档

| 内容 | 路径 |
|---|---|
| 前序交接（已脱敏） | `开发起步包/105_JHEMR密码加密逆向分析与身份同步灰度交接说明.md` |
| 执行计划 | `开发起步包/103_HIS人员向无纸化与电子病历夜间同步执行计划.md` |
| 独立复核 | `开发起步包/104_HIS人员夜间同步CDMS与JHEMR方案独立复核报告.md` |
| JHEMR 适配器 | `backend/app/services/jhemr_identity_adapter.py` |
| 身份同步编排 | `backend/app/services/identity_sync_orchestrator.py` |
| 待办总入口 | `开发起步包/55_系统未完成事项统一执行计划.md` |
