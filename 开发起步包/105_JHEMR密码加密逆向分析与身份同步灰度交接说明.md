> 类别：交接说明
> 状态：被 106 号部分取代（2026-08-01 更新；密码算法以 106 号为准，本文其余灰度与安全结论仍有效）

# 105 JHEMR 密码加密逆向分析与身份同步灰度交接说明

## 1. 结论

HIS 人员同步到 CDMS（无纸化）和 JHEMR（电子病历）的首个单用户灰度已经完成，重复 dry-run 无新增动作，HIS/HRP 业务源库写入为 0。夜间批量仍关闭。

JHEMR 密码字段为 `users.user_pwd_sm`。现有证据支持客户端使用 SM4 相关实现，并引用 `key_id=102`；真实密钥和加密前明文封装格式尚未取得，因此当前不得由同步程序生成或批量更新 JHEMR 密码。

2026-08-01 的账号管理日志新增确认：管理员将灰度账号密码修改为一个已知单字符值时，客户端在向数据库服务提交 `UPDATE USERS` 前已经生成 `USER_PWD_SM`。数据库服务只执行客户端提供的 SQL，并不负责密码加密。该日志提供了一组受控的已知明文/密文验证样本，但不能用于可行地反推出 128 位 SM4 密钥。

## 2. 灰度结果

- 一个护士账号已成功同步至 CDMS，并绑定护理质控角色、所属科室和基础授权。
- JHEMR 已补护士角色组 `002`，账号密码由管理后台人工重置。
- 同工号再次 dry-run 为 0 动作，幂等检查通过。
- 本文不记录姓名、完整工号、密码或密码密文；核验时仅通过受控审计批次定位原始证据。

## 3. 已确认的技术事实

| 项目 | 当前结论 |
|---|---|
| 密码字段 | `jhemr.users.user_pwd_sm`；`user_pwd` 基本废弃 |
| 密文外形 | 已观察样本为 Base64 编码的单个 16 字节分组 |
| 算法线索 | 客户端程序集包含 `SM4/ECB/PKCS5Padding` 和完整 SM4 ECB/CBC 实现 |
| 密钥来源 | 服务端密钥管理链路，引用 `key_id=102` |
| 客户端处理 | 账号管理客户端生成密文后，将其放入 `UPDATE USERS` 提交给数据库服务 |
| 随机性 | 不同操作样本不足以证明明文是否直接加密；可能存在随机前缀、封装或其他预处理 |
| 当前阻断 | 缺少 `key_id=102` 的受控密钥或厂商密码初始化 API，且明文封装格式未验证 |

注意：已知明文/密文对只能用于取得候选密钥后的正确性验证。对标准 SM4 而言，无法通过少量已知明文/密文对在现实计算成本内恢复 128 位密钥。

## 4. 客户端证据

本机程序目录：`F:\python\JHEMR\`。

| 文件 | 已发现内容 | 后续用途 |
|---|---|---|
| `JHNetSecuritySM.dll` | `EncryptECB`、`DecryptECB`、`EncryptCBC`、`DecryptCBC` | 确认具体 SM4 调用参数和编码规则 |
| `JHServicesLib.dll` | `SM4:102`、算法名、`TKeyDetailInfo(..., plainkey)` | 追踪密钥服务调用和返回对象 |
| `JHPubServicesLib.dll` | 数据库服务客户端与 SM4 引用 | 区分数据库请求和密钥请求 |
| `JHEMRLoginExtend.dll` | `EmrGetEncodingPassword`、`EncryptPassword`、`MD5Encrypt32` | 优先反编译方法体和调用方 |
| `JHMRCustom.dll` | SM4 ECB/CBC、`appSecretKey` | 排查其他加密链路，避免误认 |
| `JHReportDLLUpload.dll` | `secretKey`、SM4 与机构编码线索 | 仅作旁证，不直接认定为密码算法 |

普通字符串扫描无法还原方法体。后续应使用 ILSpy/dnSpy 对托管程序集做静态反编译；程序集为 x86 不影响静态反编译，只影响直接在 64 位 PowerShell 中加载执行。

## 5. 正确的后续调查顺序

1. 使用 ILSpy/dnSpy 打开 `JHEMRLoginExtend.dll`，导出 `EmrGetEncodingPassword` 和 `EncryptPassword` 的完整方法体、参数类型、调用方与依赖程序集。
2. 在所有调用方中追踪 `key_id=102`、`TKeyDetailInfo.plainkey` 和 `JHNetSecuritySM.Sm4ExternalMethod.EncryptECB` 之间的数据流，确认密钥是 hex、UTF-8 文本还是其他编码。
3. 在用户授权的测试终端上，通过 Fiddler/Wireshark 或 .NET 运行时跟踪捕获“密钥服务请求的接口名、参数结构和返回字段”。抓取物必须留在受控目录，不进入 Git、聊天或普通日志。
4. 优先向厂商索取正式密码初始化/重置 API。若有 API，同步程序应调用受控 API，不直接持有 SM4 主密钥。
5. 只有取得候选密钥后，才使用受控证据中的已知明文/密文对离线验证算法、编码、填充和随机前缀格式。

不建议把精力放在穷举密钥上。标准 SM4 的 128 位密钥空间使该方法不可行。

## 6. 目标表与角色规则

### 6.1 JHEMR

```text
users:
  PK=(db_user, hospital_no), user_id, user_login_name,
  user_pwd, user_pwd_sm, pwd_modify_time,
  account_status, state, user_type, hospital_no

jhauth_user_vs_role_group:
  user_id, role_group_id, hospital_no

user_dept:
  user_id, user_dept, hospital_no,
  synchro_flag, default_dept_flag, state
```

- 生产租户键固定使用医院机构编码，不依赖数据库列默认值。
- 医师和药师绑定角色组 `001`；护士绑定角色组 `002`。
- 只维护用户角色组和科室，不复制参考账号的直接角色或直接权限。
- 在密码算法未封板前，不写 `user_pwd`、`user_pwd_sm` 或 `pwd_modify_time`。

### 6.2 CDMS

```text
T_MSS_EMP_DICT:
  FLOGINNAME, FUSERNAME, FPWD, FPOSITION, FDEPT, FROLEID,
  FSYSID, FUSERTYPE, FUSERSTATE, HOSPITALAREACODE

T_MSS_AUTHMAPPING:
  FAUTHMAPPINGID, FID, FAUTHORITYID, FTYPE,
  FDATE, FUSER, FST, FPRIVIEGETYPE
```

- 医师和药师绑定医疗质控角色；护士绑定护理质控角色。
- CDMS 初始密码密文只能在运行时从目标库按受控规则读取模板，不得写入代码、文档、配置或审计日志。

## 7. 凭据与连接边界

- SSH 使用受控公钥，不在文档记录 SSH 密码。
- HIS 凭据只读；CDMS 与 JHEMR 写凭据分别从以下受控引用读取：
  - `file:///etc/data-asset/credentials/cdms_identity_sync.write`
  - `file:///etc/data-asset/credentials/jhemr_identity_sync.write`
- 应用和测试数据库连接串必须由环境变量或受控凭据提供，禁止在命令、文档、代码和日志中展开密码。
- 会话中曾暴露的数据库密码应轮换；本文不保留其值。

## 8. 密钥验证模板

以下仅是结构模板，不包含真实密钥、密文或密码。验证脚本必须在隔离环境读取受控证据文件，输出仅限布尔结果和长度，不输出明文、密钥或完整密文。

```python
from base64 import b64decode
from gmssl.sm4 import CryptSM4, SM4_DECRYPT

key = resolve_secret("jhemr-sm4-key-102")
sample = load_controlled_sample("jhemr-password-known-pair")

sm4 = CryptSM4()
sm4.set_key(key, SM4_DECRYPT)
decrypted = sm4.crypt_ecb(b64decode(sample.ciphertext_b64))
assert validate_password_envelope(decrypted, sample.expected_password)
print({"verified": True, "block_count": len(b64decode(sample.ciphertext_b64)) // 16})
```

`resolve_secret`、`load_controlled_sample` 和 `validate_password_envelope` 是待实现的受控接口，不应替换成代码常量。

## 9. 自动化放行门禁

只有同时满足以下条件，才允许实现并灰度 JHEMR 密码初始化：

1. 厂商 API 或 `key_id=102` 密钥来源、授权和轮换方式已书面确认。
2. 已知样本验证通过，明确密钥编码、明文封装、随机因子、填充方式和 Base64 规则。
3. 单元测试不包含真实密钥、密码或生产密文。
4. 密钥由受控 secret provider 注入，应用日志和审计对密码字段强制剔除。
5. 仅对一个测试/灰度账号执行，先 dry-run，再经人工审批 apply，并完成登录验证和回滚验证。
6. 未满足上述门禁时，继续由 JHEMR 管理后台人工初始化密码。

## 10. 当前禁止事项

- 禁止根据已知明文/密文对尝试穷举 SM4 密钥。
- 禁止将客户端日志中的姓名、工号、密码密文或 SQL 原文提交到 Git 或普通报告。
- 禁止未经授权从生产服务内存、配置或网络流量提取密钥。
- 禁止直接批量更新 `users.user_pwd_sm`。
- 禁止启动夜间多用户 apply；当前只允许继续完善 dry-run、分类、角色和科室同步逻辑。

## 11. 代码位置

| 内容 | 路径 |
|---|---|
| 身份同步编排 | `backend/app/services/identity_sync_orchestrator.py` |
| CDMS 适配器 | `backend/app/services/cdms_identity_adapter.py` |
| JHEMR 适配器 | `backend/app/services/jhemr_identity_adapter.py` |
| 分类器 | `backend/app/services/identity_classification.py` |
| API | `backend/app/api/v1/identity_sync.py` |
| 测试 | `backend/tests/test_identity_sync.py` |
| 执行计划 | `开发起步包/103_HIS人员向无纸化与电子病历夜间同步执行计划.md` |
| 独立复核 | `开发起步包/104_HIS人员夜间同步CDMS与JHEMR方案独立复核报告.md` |
