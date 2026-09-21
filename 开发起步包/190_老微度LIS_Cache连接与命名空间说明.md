> 类别：当前
>
> 状态：**已接入（2026-09-15 平台登记：系统 LIS_CACHE + 源 lis_cache_10_10_10_70，审计 1 行；JDBC 与门户 Web SQL 双通道实测打通）**
>
> 用途：老微度 LIS（InterSystems Cache/Ensemble）的唯一连接与探查入口——后续 AI 取数、探表、统计一律从本文件出发。

# 老微度LIS（Cache）连接方式与命名空间版图

## 1. 身份事实（2026-09-15 实测）

| 项 | 值 |
|---|---|
| 软件 | InterSystems **Ensemble/Cache 2010.1.1.503**（Cache xDBC Server 8.01；非 Oracle——187 C 类旧记"LIS Oracle"有误，已勘误） |
| 端点 | 10.10.10.70:1972（xDBC/JDBC）/ 57772（CSP 管理门户） |
| 物理主机 | **WIN-L8RLDJSU610——与病案 YCYL 库 10.10.10.55 同一台 Windows 主机（多 IP）**，资产物理映射按同机去重 |
| 账号 | 专用只读账号（凭据文件见 §2，**只允许 SELECT**；`_system` 为超级用户勿用） |
| 平台登记 | system_code=`LIS_CACHE`，source_code=`lis_cache_10_10_10_70`，db_type=**cache**（新库型），write_policy=readonly |

## 2. 连接方法（8.83 容器/宿主专用工具包）

**sjzc live 连接器不支持 cache 库型——不要用 `/sjzc live` 连它**。统一走 8.83 上已布好的工具包：

```bash
# 一键探查（默认命名空间 LIS3；凭据自动从受控文件读，不进命令行）
ssh root@10.10.8.83 "bash /opt/data-asset/cache-jdbc/probe.sh LIS3"            # 全表清单
ssh root@10.10.8.83 "bash /opt/data-asset/cache-jdbc/probe.sh LIS3 '%Pattern%'" # 按表名模式+行数
```

组件位置：JRE8=`/opt/jre8u504/`，驱动=`/opt/data-asset/cache-jdbc/CacheDB.jar`（2010 版，与服务器同代），探针源码同目录 `JDBCProbe.java`。凭据文件=`/etc/data-asset/credentials/lis_cache_10_10_10_70`（0600，格式 `user:password`，**勿写入任何文档/仓库**）。

JDBC URL 格式：`jdbc:Cache://10.10.10.70:1972/<命名空间>`（命名空间=库，见 §3）。

**备选通道（免登录 Web SQL，应急用）**：门户 `http://10.10.10.70:57772/csp/sys/exp/UtilSqlQuery.csp` 当前免认证可执行 SQL（脚本：8.83 容器 `/tmp/websql.py <命名空间> "<SQL>"`，需重传时源码在本仓库 `_scratch/cache_probe/websql.py`）。⚠️ 门户整站免认证是重大安全隐患（见 §5），仅作应急，不作为常规通道。

## 3. 命名空间版图（= 库清单，2026-09-15 只读摸底）

| 命名空间 | SQL 表数 | 内容 |
|---|---:|---|
| **LIS3** | 206 | 检验业务主库：EMR.LIS_RESULT/EMR.LIS_TEST_REG、金域 Kingmed.*、东大基因 Dongdajy.*、LAB302.*、微生物 MIC3.*、MSG*/MSG_PLab 消息、PLab.CChargeLog 收费日志 |
| **HIS** | 121 | HIS 集成镜像：LAB.LAB_RESULT / LAB_TEST_MASTER / PAT_MASTER_INDEX / INP_BILL_DETAIL / DOCTOR_ORDERS / PATS_IN_HOSPITAL 等 |
| ISO | 215 | 仪器接口层 |
| LIB / ENSEMBLE | 156 | 系统库 |
| LAB | 18 | 字典与价格（CLabRef/CLabTest/CPriceBook/CProfile…） |
| LIS-QC | 10 | 质控（PQC.*） |
| HMIS | 17 | 住院/科室/设备（PHospital.*） |
| ANA | 13 | 用户权限（PSystem.CUser/CUserAccess…） |
| 其他 | — | BIZ(1)/GDI(0)/USER(1)/%SYS/SAMPLES/DOCBOOK/ENSDEMO/ENSLIB |

注意：用户 DBeaver 曾查询的 `RPC_BlackCharges` 未在任何命名空间 SQL 表层出现（可能未投影为 SQL 表）——后续 AI 遇到该表先向用户确认所在命名空间，勿假设。

## 4. 已知陷阱（不读会白排查一小时）

1. **命名空间不存在 → JDBC 报 `Access Denied`**，与密码错误完全同貌。连不上先核命名空间拼写（无小写 `lis`，是 `LIS3`）。
2. **2010 版驱动是 JDBC3 时代**：Java 端必须显式 `Class.forName("com.intersys.jdbc.CacheDriver")`，JDBC4 自动注册无效（JDBCProbe 已内置）。
3. DBeaver 在**服务器本机 localhost** 可连是走本机通道；远程一律用 §2 工具包。
4. 老 Cache SQL 限行用 `TOP n`（无 `FETCH FIRST`）；聚合统计优先 `GROUP BY` + `COUNT/SUM`，勿全量拉明细。

## 5. 安全事项（待用户/厂商处理）

- 管理门户 57772 **整站免认证**（UnknownUser 可浏览安全配置并执行 SQL）；
- `Allow Unauthenticated access=✔`；`_system` 弱口令、只读账号弱口令——建议轮换；
- Cache 2010 已无厂商支持，长期纳管建议评估迁移。

## 6. 关联记录

- 接入过程与排障实录：本文件 §4 即结论；凭据建设沿 188 号账号规范（专用只读账号+受控文件 0600）。
- 平台登记审计：`asset_govern_audit_logs` operator=r190_cache_lis（2026-09-15）。
- 187 §3 C 类旧条目"LIS Oracle 10.10.10.70 容器网络不通"→ 已勘误（网络通、库型 Cache、已登记 B 类外新增源）。

## 7. 工具沉淀（2026-09-15 统计任务产出）

8.83 `/opt/data-asset/cache-jdbc/` 下新增（源码同存于仓库 `_scratch/cache_probe/`）：
- **QueryTool.java**：只读 SQL 工具（cols 列结构 / sql 单条 SELECT，480s 超时，SELECT/WITH 白名单）；
- **BatchCount.java**：大规模计数器——主键 ID 分段扫（每批 2 万）+ Java 内存**按标本条码去重**聚合 + 工号/姓名双匹配 + 抽样条码输出；老库无列索引时 SQL COUNT 会超时，一律用它。

统计核查要点（后续同类任务必读）：老库常规检验 2023-01 起与新瑞美 LIS **双写**（2023-05 抽样 98.2% 条码交集），跨 2023 年的统计必须以 2022-12-31/2023-01-01 分界两库分段；老库微生物 MIC3.*/PLinkMic.* SQL 投影损坏（游标开不了，需厂商修复）；先例交付见 `取数/exports/17、检验报告签发量统计（职称晋升）/`。
