QMToolV7/
├── interfaces/
│   ├── cli/
│   │   ├── main.py                    # CLI entry point
│   │   ├── commands/                  # Command handlers
│   │   └── parsers/                   # Argument parsers
│   ├── pyqt/                          # Active GUI (source of truth)
│   │   ├── main.py
│   │   ├── shell/                     # Main window, navigation
│   │   ├── registry/catalog.py      # Contribution registry
│   │   ├── contributions/           # Module UI contributions
│   │   ├── presenters/              # View presenters
│   │   ├── sections/                # Reusable UI sections
│   │   └── widgets/                 # Shared widgets/dialogs
│   └── gui/
│       └── main.py                    # Legacy Tk (test-only)
├── modules/
│   ├── documents/
│   ├── signature/
│   ├── usermanagement/
│   ├── registry/
│   ├── training/
│   └── incident_management/
├── qm_platform/
│   ├── runtime/                       # Container, bootstrap, lifecycle
│   ├── events/                          # Event bus/envelopes
│   ├── settings/                        # Settings registry/store/service
│   ├── licensing/                       # License guard/service/policy
│   └── logging/                         # Platform and audit logging
├── src/backend/                         # Backend transport host
│   ├── api.py                           # Public backend API
│   └── __main__.py                      # Backend entry point
├── packaging/                           # Build scripts and gates
├── tests/                               # Unit, matrix, e2e CLI, UI smoke
├── docs/                                # Architecture and usage guides
└── storage/                           # Runtime data (settings, logs, DBs, artifacts)
