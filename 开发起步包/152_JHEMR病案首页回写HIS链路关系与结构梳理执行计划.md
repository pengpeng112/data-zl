> 类别：模块规划
>
> 状态：**已执行完成（2026-08-26，E1–E6 一次跑完；结果与全部证据见 `152_JHEMR病案首页回写HIS链路梳理_结果.json`）**
>
> 上位入口：`55_系统未完成事项统一执行计划.md`
>
> 关联文档：`151_两字典表批量接入值域知识库与待核值域收口执行计划.md`（本计划 E5 产物是其 E2 圈定的映射依据）、`149_字段值域知识库与AI自动注入执行计划.md`（值域库语义）、`135_病案首页是否非计划再入院字段口径说明.md`（回写链路已知坑）、`77_JHEMR海量数据库只读探查与资产导入报告.md` + `数据资产_JHEMR_Vastbase资产包/`（4 视图列与依赖底账）、`148_病案首页关键值域与离院方式口径字典.md`

# JHEMR 病案首页回写 HIS 链路关系与结构梳理执行计划（152）

## 0. 背景与目标

用户 2026-08-26 提供回写链路入口（JHEMR 侧按 `patient_id + visit_id` 取数）：

```sql
select * from v_HISshouye    where patient_id='{1}' and visit_id={2};
select * from v_HISshoushu   where patient_id='{1}' and visit_id={2};
select * from v_HISzhenduan  where patient_id='{1}' and visit_id={2};
select * from v_HISicu       where patient_id='{1}' and visit_id={2};
```

并要求把「JHEMR 首页数据 → 4 个回写视图 → 老 HIS 程序 `d:\Users\Administrator\Desktop\嘉和\老his\server_test` → 写入 HIS 库」这条链路的**关系与结构**梳理清楚。

**目标**（一次性完成）：
1. 确认并落盘回写链路全景：视图 → SATRDA 中间件端点 → PB 插件 → HIS 目标表，字段级映射 + 转码规则；
2. live 核验（只读）四视图当前 DDL 与 HIS 目标表实际结构，确认离线结论无漂移；
3. 产出机器可读结果 `152_..._结果.json`（链路、映射、写库 SQL 清单、核验证据），供关系图谱候选与 151 值域圈定复用；
4. 衔接 151：回写链路涉及的值域转码点（`emr_first_page_item_dict` 被 4 视图引用）整理成候选清单，交 151 E2 圈定参考。

**非目标**：不修改/重启/停止 server_test 程序（生产在用）；不反编译 PBD（仅只读字符串提取）；不修复 135 已发现的回写丢值问题（只梳理、出建议）；不写任何业务库/生产平台库；不执行 151 的导入本体；不把回写关系直接升正式关系资产（走候选复核流程）。

## 1. 离线分析结论（2026-08-26 已完成，本计划的证据底账）

### 1.1 链路全景（离线已确认）

```text
医生在 JHEMR 填病案首页
    → jhemr.pat_visit1 / pat_diagnosis / operation（现用表）
         ↘（定时/触发快照，分叉点，见 135）
    → report.r_pat_visit / r_pat_visit1 / r_operation_doct / r_diagnosis_doct / r_grave_ward_detail（报表快照）
         → jhemr.v_HISshouye / v_HISshoushu / v_HISzhenduan / v_HISicu（回写视图，内嵌转码 CASE + 引 emr_first_page_item_dict）
              → POST http://<server_test>:9008/pbtest/api/his/basy（SATRDA 中间件 ljserver2.exe）
                   → plugins/test/plugin.pbd（basy 路由）→ testdemo.pbd（写库 SQL）
                        → HIS 库（dbconfig mycon2，SEC=true 加密连接串）：先 DELETE 再 INSERT 全量替换 + pat_visit UPDATE
```

### 1.2 四视图结构（77 资产包实测列，执行 AI 须 live 复核漂移）

| 视图 | 列数 | 静态依赖（pg_views，B 级候选） | 关键列 |
|---|---|---|---|
| `jhemr.v_hisshouye` | 67 | `report.r_pat_visit`、`report.r_pat_visit1`、`jhemr.pat_diagnosis`、`jhemr.emr_first_page_item_dict` | patient_id/visit_id/trt_type/discharge_date_time/discharge_disposition/护理天数×4/blood_type(_rh)/alergy_drugs/mr_quality/三级医师与质控/plan_admission/plan_31_admission/肿瘤/临床路径/tumor_stage 等 |
| `jhemr.v_hisshoushu` | 21 | `report.r_operation_doct`、`jhemr.emr_first_page_item_dict` | operation_no/operation_desc/operation_code/heal/wound_grade/operating_date/anaesthesia_method/operator/助手×2/anesthesia_doctor/operation_emer_indicator/operation_scale |
| `jhemr.v_hiszhenduan` | 14 | `report.r_diagnosis_doct`、`jhemr.pat_visit1`、`jhemr.emr_first_page_item_dict` | diagnosis_type/diagnosis_no/diagnosis_desc/diagnosis_date/treat_days/treat_result/oper_treat_indicator/diagnosis_code(_2)/admission_condition |
| `jhemr.v_hisicu` | 6 | `report.r_grave_ward_detail`、`jhemr.emr_first_page_item_dict` | icu_type/into_icu_date/out_icu_date/hours |

- 另有 `v_hisshouye1`（134 列，直读现用表 pat_visit1 等）、`v_hisshoushu1`、`v_hiszhenduan1` 变体；**当前回写用不带 `1` 的版本**（135 已确认，135 建议中"改读现用表"对应 `*1` 变体，仅记录不实施）。
- 135 已验证的转码样例：`CASE WHEN b.sffjhzry='是' THEN '1' WHEN '否' THEN '2' ELSE b.sffjhzry END AS plan_admission`；执行 AI 须在 E2 把 4 视图全部 CASE 转码点抽全。

### 1.3 server_test 程序勘察（本机文件只读，2026-08-26 已做初勘）

| 项 | 事实 |
|---|---|
| 程序形态 | SATRDA 中间件 `ljserver2.exe`（PB 三层：satrda.dll + PbIdea.dll/pbfunc.dll + PBD 插件），HTTP 端口 9008（`config/config`，Log=1） |
| 唯一活跃端点 | `POST /pbtest/api/his/basy`（basy=病案首页）；log20260817–0823 共 **7046 次 POST + 1 次 GET**，调用方 IP 10.10.8.1（约每分钟 1 次，回写在活跃运行） |
| 数据库连接 | `config/dbconfig`：`mycon2`（ODBC，Provider 已加密 `SEC:true`，**禁止尝试解密、禁止复制该串**）；mycon1/mycon3 为出厂示例串 |
| 业务逻辑位置 | `plugins/test/plugin.pbd`（含 "basy" 路由串）；`plugins/test/testdemo.pbd`（含全部回写写库 SQL，明文可提取） |
| 证书/杂项 | `config/certs/server.crt|key`、`pay.cfg`、`qiniucfg`、`restful/restful.cfg|session.cfg`（E2 只读过一遍，确认无其他 his 相关端点） |

### 1.4 回写写库 SQL 清单（testdemo.pbd 字符串提取证据，模式 = 先删后插全量替换）

| 首页子块 | HIS 目标表 | 操作 | 证据摘录 |
|---|---|---|---|
| 首页主表 | `pat_visit` | UPDATE ×2（一条仅护理天数，一条全字段：`patient_class/pat_adm_condition/护理天数×4/blood_type(_rh)/alergy_drugs/mr_quality/director/attending_doctor/doctor_in_charge/disch…` 被截断，**E2 须抽全，重点确认是否含 discharge_disposition**） | `update pat_visit a SET a.patient_class=…` |
| 首页附表 | `pat_visit_extend` | DELETE + INSERT（PATIENT_ID/VISIT_ID/PLAN_ADMISSION/DAY_WARD/DUTY_NURSE1–5） | `insert into pat_visit_extend (PATIENT_ID,VISIT_ID,PLAN_ADMISSION,DAY_WARD,DUTY_NURSE1…)` |
| 手术 | `OPERATION` | DELETE + INSERT（21+ 列，含 `SOURCE` 来源标记、OPERATION_EMER_INDICATOR、OPERATING_END_DATE） | `INSERT INTO OPERATION (PATIENT_ID,VISIT_ID,OPERATION_NO,…,SOURCE,…)` |
| 诊断 | `DIAGNOSIS` | DELETE + INSERT + UPDATE（DIAGNOSIS_TYPE/NO/DESC/DATE/TREAT_DAYS/TREAT_RESULT/OPER_TREAT_INDICATOR/…） | `INSERT INTO DIAGNOSIS (PATIENT_ID,VISIT_ID,DIAGNOSIS_TYPE,…)` |
| ICU | `pat_icu_record` | DELETE + INSERT（patient_id/visit_id/icu_no/icu_type/into_icu_date/out_icu_date/hours） | `INSERT INTO pat_icu_record (patient_id,visit_id,icu_no,…)` |
| 病案评阅 | `MEDICAL_RECORD_REVIEW_TABLE` | 计数 SELECT + INSERT（mr_falg=1）+ UPDATE MR_NUMBER（回写后登记评阅任务） | `select nvl(count(*),0),MR_NUMBER from MEDICAL_RECORD_REVIEW_TABLE …` |

- 注意 owner：testdemo.pbd SQL 均未带 schema 前缀，目标 owner 由 mycon2 连接用户决定，E3 须 live 确认（135 已确认 `MEDREC.PAT_VISIT_EXTEND` 是 SFFJHZRY 实际落点）。
- 与 135 已知坑一致：空值会被写成默认 2；`v_HISshouye` 读快照与现用表分叉（822 条不一致、约 3.5 万条只在现用表）。

## 2. 执行步骤

| 步 | 内容 | 产出 |
|---|---|---|
| E1 | **JHEMR live 核验（sjzc 只读）**：pg_views 拉取 4+4（含 `*1` 变体）视图完整 DDL；核对列清单与 77 资产包是否漂移；抽取全部 CASE/字典转码点；`report.*` 快照表行数与最新更新时间 vs 现用表（聚合口径，限量） | DDL 与转码点清单 |
| E2 | **server_test 静态勘察（本机文件只读）**：全量历史 log 端点统计与错误行抽样；restful.cfg/session.cfg 过一遍；testdemo.pbd/plugin.pbd 字符串提取补全 §1.4 被截断的 SQL（重点：update pat_visit 全列清单——是否含 discharge_disposition 等值域字段）；确认无 basy 以外 his 写端点 | 完整写库 SQL 清单 |
| E3 | **HIS 侧 live 核验（sjzc/HIS_SOURCE 只读）**：5 张目标表（pat_visit/pat_visit_extend/OPERATION/DIAGNOSIS/pat_icu_record + MEDICAL_RECORD_REVIEW_TABLE）实际列结构；回写证据聚合验证（OPERATION.SOURCE 值分布、pat_icu_record 行数与近期增量、pat_visit_extend.PLAN_ADMISSION 分布复核 135 口径）；限量抽样对账视图↔HIS 目标表一致性（ROWNUM 限量、患者标识前2后2脱敏） | 目标表结构 + 核验证据 |
| E4 | **字段级映射表**：每视图列 → HIS 目标列 → 转码规则 → 已知坑标注（135）；4 张映射表落 152 结果 JSON | 映射表 |
| E5 | **值域衔接清单**：回写链路涉及的编码字段（discharge_disposition/trt_type/blood_type/mr_quality/treat_result/heal/wound_grade/anaesthesia_method/admission_condition/diagnosis_type/icu_type 等）× 视图转码点 × emr_first_page_item_dict FIELD_NAME，整理成候选值域清单，供 151 E2 圈定与 E5 离院方式 code9 核查引用；不在本计划内导入值域库 | 候选值域清单 |
| E6 | **收口**：`152_JHEMR病案首页回写HIS链路梳理_结果.json` 落盘并登记 README/55；回写链路关系（4 视图→HIS 目标表、视图→report 快照）按 `.agents/skills/sql-relation-intake` 走候选分级，**不得直接写正式关系**；对 135 修复建议只登记不实施 | 结果 JSON + 登记 |

## 3. 安全与禁止（执行 AI 硬约束）

- 业务源库（JHEMR Vastbase / HIS）**一律只读 SELECT**，聚合优先 + ROWNUM 限量，走 sjzc 受控通道；大表禁全扫；
- server_test 是**在用生产程序**：只读其文件，禁止修改/移动/重启/停止任何文件与进程；`dbconfig` 加密连接串禁止解密尝试、禁止复制到任何输出；
- 日志/PBD 内容可能含 patient_id：报告与 JSON 一律前2后2脱敏，姓名/身份证禁止出现；
- 禁止 Git push/tag、禁止生产平台库写入、禁止 confirm 任何值域；
- 不改动 126/144/146/149/151 既有文件语义；与 151 的关系仅为"提供候选清单"，不代替 151 执行。

## 4. 验收

1. `152_JHEMR病案首页回写HIS链路梳理_结果.json` 存在且含：链路图、4+4 视图 DDL 漂移结论、完整写库 SQL 清单（无截断）、4 张字段映射表、E3 聚合核验证据、E5 候选值域清单；
2. 报告如实标注每项证据来源（live/资产包/PBD 字符串）与跳过项原因；
3. README「模块计划」与「目录更新记录」、55 顶部 📌 各补一行；
4. 业务源库 DML/DDL=0、server_test 文件零改动（执行前后 `ls -l` 时间戳比对）。

## 5. 执行提示词（交给执行 AI，逐条执行）

```
【任务】一次性执行 开发起步包/152_JHEMR病案首页回写HIS链路关系与结构梳理执行计划.md 的 E1→E6。

【开工前必读（按序）】
1. AGENTS.md（硬约束：探库只读、ROWNUM 限量、脱敏、安全红线；文档管理 4 步）
2. 开发起步包/152_*.md —— 唯一执行依据（§1 离线结论是你的证据底账，先核对再补充，不得推翻后无证据改写）
3. 开发起步包/135_病案首页是否非计划再入院字段口径说明.md（回写已知坑与脱敏口径）
4. 开发起步包/数据资产_JHEMR_Vastbase资产包/（tables/columns/relationships.csv：4 视图列与依赖底账）
5. 全局技能 ~/.zcode/skills/sjzc/SKILL.md（唯一连库通道）

【E1 JHEMR live 核验（只读）】
- sjzc 查 JHEMR 系统 pg_views：v_hisshouye/v_hisshoushu/v_hiszhenduan/v_hisicu 及 *1 变体完整 DDL 导出（DDL 可长，落结果 JSON 原样保存）；
- 列清单与 77 资产包逐列比对，漂移处记录；
- 从 DDL 抽取全部 CASE 转码点与 emr_first_page_item_dict 引用点；
- report.r_pat_visit/r_pat_visit1/r_operation_doct/r_diagnosis_doct/r_grave_ward_detail 行数 + 最大时间列 vs 对应现用表（聚合，限量）。

【E2 server_test 静态勘察（本机只读）】
- d:\Users\Administrator\Desktop\嘉和\老his\server_test\：log 全量端点统计（grep -ho "POST [^ ]*\|GET [^ ]*" log* | sort | uniq -c）与错误行抽样（脱敏）；
- config/restful/*.cfg、plugins/config.cfg 只读过一遍，确认无 basy 以外 his 端点；
- 用 strings/正则从 plugins/test/testdemo.pbd、plugin.pbd 提取全部含 insert/update/delete/select 的长字符串，补全 152 §1.4 被截断 SQL（重点：update pat_visit 的完整 SET 列清单——记录是否含 discharge_disposition/trt_type 等值域字段）；
- 禁止修改/重启/停止任何程序文件与进程；dbconfig 加密串不解密不复制。

【E3 HIS 侧 live 核验（只读）】
- sjzc 查 HIS 源端：MEDREC.pat_visit / pat_visit_extend / OPERATION / DIAGNOSIS / pat_icu_record / MEDICAL_RECORD_REVIEW_TABLE 实际列结构（确认 owner 与列存在性）；
- 聚合证据：OPERATION.SOURCE 值分布（GROUP BY 限量）；pat_icu_record 总行数与近 30 天增量；pat_visit_extend.PLAN_ADMISSION 分布（复核 135：是否仍全 2）；
- 视图↔目标表抽样对账：取 v_hisshouye ROWNUM<=5 的就诊键，对 HIS 侧同键行做字段级一致性比对（患者标识前2后2脱敏后入报告）。

【E4 字段级映射表】
- 按 152 §2 E4 产出 4 张映射表（视图列→HIS 目标列→转码规则→坑位标注），落入结果 JSON。

【E5 值域衔接清单】
- 按 152 §2 E5 产出候选值域清单（编码字段×转码点×FIELD_NAME），标注"供 151 E2 圈定参考，本计划不导入"。

【E6 收口】
- 落盘 开发起步包/152_JHEMR病案首页回写HIS链路梳理_结果.json；
- README 模块计划+目录更新记录、55 顶部 📌 各登记一行；
- 回写链路关系按 .agents/skills/sql-relation-intake/SKILL.md 走候选分级，禁止直接写正式关系；
- 报告如实注明跳过项与原因；声明业务源库 DML/DDL=0、server_test 零改动。

【禁止】连生产平台库/业务源库写；修改 server_test 任何文件或进程；解密/复制 dbconfig 连接串；confirm 值域；Git push/tag；改 126/144/146/149/151 语义；患者标识或凭据进入任何输出。
```

## 6. 风险与待确认

| # | 事项 | 处理 |
|---|---|---|
| R1 | `update pat_visit` 完整列清单在 PBD 中可能被截断/分段存储 | E2 多种提取策略（不同最小长度、GBK/UTF-16 双编码扫描）；仍不全则在结果 JSON 标 `PARTIAL` 并给出已确认列 |
| R2 | mycon2 连接用户未知 → HIS 目标表 owner 推断可能错 | E3 以 live 列存在性 + 135 已确认的 MEDREC.PAT_VISIT_EXTEND 交叉定位；无法确认的 owner 标"待确认" |
| R3 | 视图 DDL 较 77 采集时（2026-07）已漂移 | E1 live 为准，漂移写入结果 JSON 差异段 |
| R4 | report.* 快照刷新机制（定时/触发器/手工）本计划不可知 | 仅记录行数与最新时间证据，机制问题列入"待确认"交用户问嘉和实施 |
| R5 | 151 与本计划并行执行时 E5 清单可能时滞 | 本计划 E5 只出清单不动库；151 导入时以其自身 live 核查为准 |
