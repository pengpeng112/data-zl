with q(table_name) as (values
('BD_DEFDOC'),('BD_PSNCL'),('BD_PSNDOC'),('HI_PSNDOC_EDU'),('HI_PSNDOC_GLBDEF2'),('HI_PSNJOB'),('MD_ENUMVALUE'),('ORG_DEPT')
)
select q.table_name, t.system_code, t.schema_name, t.source_code
from q join asset.asset_tables t on upper(t.table_name)=q.table_name
order by 1,2;
