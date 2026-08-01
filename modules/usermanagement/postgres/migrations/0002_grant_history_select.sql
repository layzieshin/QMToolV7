-- AP-028 M5: Runtime may read schema history for readiness checks.
-- No DML on `_qm_schema_migrations` — SELECT only.

GRANT SELECT ON usermanagement._qm_schema_migrations TO qmtool_runtime;
