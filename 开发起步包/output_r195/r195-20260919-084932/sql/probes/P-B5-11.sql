-- probe P-B5-11 | pathology_sqlserver_10_10_9_41 | sqlserver
-- question: Status=512 含义与分布（195 §2.2 遗留问题）
-- scope: 病理主表聚合
-- note: 
SELECT TOP 20 Status, COUNT(*) n FROM dbo.Pitaya GROUP BY Status ORDER BY n DESC
