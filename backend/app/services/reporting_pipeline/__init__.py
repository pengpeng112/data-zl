"""R189-T1 Python/DataX 统一T+1抽取工程（包 R189-T1-ENGINEERING-20261019-v1.2）。

分层：contracts（契约/就绪分层/状态机）→ planner/repositories（控制面）→
adapters（读取）→ staging/quality（暂存与质量）→ apply_port/reconcile（受控装载
与对账）→ recovery/scheduler_bridge/alerts（恢复、调度与企微v2告警）。

本包只实现本地软件能力；77项任务默认 disabled/UNKNOWN，生产读/写/发布动作
按原计划分批门禁，不因代码存在而获得授权。
"""
