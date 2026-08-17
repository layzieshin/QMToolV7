# J04-M0 real-process acceptance harness (test-only)

This directory contains **test-only** orchestration for the J04-M0 final acceptance
gate. It is not a product CLI, entrypoint, or alternate backend port contract.

## Components

| File | Role |
| --- | --- |
| `j04_m0_realprocess_harness.py` | Starts `python -m src.backend` on `127.0.0.1:8000`, tracks self-spawned PIDs, redacts logs |
| `j04_m0_client_worker.py` | Standalone client subprocess with in-memory session via `BackendSessionApi` |
| `j04_m0_acceptance_scenario.py` | Ordered CP08 scenario orchestrator (CP08-R2) |
| `test_j04_m0_harness_unit.py` | Harness lifecycle/unit tests (CP05) |
| `test_j04_m0_acceptance_scenario_unit.py` | Scenario contract/unit tests (CP08-R2) |
| `test_j04_m0_realprocess.py` | Full acceptance scenario (CP08; marker + opt-in gated) |

## Environment

| Variable | Purpose |
| --- | --- |
| `QMTOOL_J04_FINAL_ACCEPTANCE` | Must be `I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN` for the full gate |
| `QMTOOL_J04_WORD_COM_LIVE` | Separate opt-in for Word COM live inside the scenario (`I_UNDERSTAND_THIS_IS_A_REAL_WORD_COM_RUN`) |
| `QMTOOL_PG_TEST_*` | Guard-approved destructive target; major is selected by `QMTOOL_PG_TEST_EXPECTED_MAJOR` (CI PG16, local CP04-R PG18; see `tests/postgres/README.md`) |
| `QMTOOL_BACKEND_URL` | Client worker backend URL (defaults to `http://127.0.0.1:8000`) |
| `QMTOOL_HOME` | Separate homes for backend and each client worker |

Logs and evidence belong under `build/j04-m0-closure/` only (never committed).

## CP08 realprocess workspace (CP08-R3)

The full gate does **not** use pytest `tmp_path` for the long-lived backend/client homes.
`allocate_realprocess_workspace()` creates a unique directory:

```text
build/j04-m0-closure/cp08-realprocess-ws/<UTC-timestamp>-<uuid>/
```

The path is `resolve()`-enforced under `repo_root()/build/j04-m0-closure/`. Existing paths are
never reused or deleted. Pytest `--basetemp` for the gate must be a **new** directory each run.

The full realprocess gate **must** start through `scripts/run_postgres_live_tests.py`. That
runner performs the read-only PG preflight and injects `QMTOOL_PG_TEST_RESET` only into the
pytest child. Direct pytest of `test_j04_m0_realprocess.py` is not a supported start contract:
`prepare_live_environment()` correctly refuses to run destructive schema work without RESET,
and a separate pytest process does not inherit the child-only injection from a prior live run.

The runner does **not** set `QMTOOL_J04_FINAL_ACCEPTANCE` or `QMTOOL_J04_WORD_COM_LIVE`.
Word COM live remains a separate opt-in after the start contract succeeds.

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$env:QMTOOL_PG_TEST_EXPECTED_MAJOR = "18"
$env:QMTOOL_J04_FINAL_ACCEPTANCE = "I_UNDERSTAND_THIS_IS_A_REAL_ACCEPTANCE_RUN"
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$Base = "build/j04-m0-closure/cp08-pytest-$stamp"
$Py scripts/run_postgres_live_tests.py `
  --j04-final-acceptance `
  --basetemp $Base
```

## CP05 scope

Run harness unit tests only:

```powershell
$Py = ".\.venv\Scripts\python.exe"
$env:PYTHONPATH = "."
$Py -m pytest tests/acceptance/test_j04_m0_harness_unit.py `
  tests/backend/test_documents_http_api.py `
  -k "two_clients_and_restart_readback or version_read_after_restart or harness" `
  -m "not postgres and not j04_final_acceptance" -q `
  --basetemp build/j04-m0-closure/cp05
```

The full `test_j04_m0_realprocess.py` module is excluded until CP08.
