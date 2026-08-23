-- AP-029 PG01-A: Runtime may read schema history for readiness checks.
-- No DML on `_qm_schema_migrations` — SELECT only.

GRANT SELECT ON signature._qm_schema_migrations TO qmtool_runtime;
