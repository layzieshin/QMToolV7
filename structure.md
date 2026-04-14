QmToolPyV4/
├── interfaces/
│   ├── cli/
│   │   └── main.py                    # CLI entry point
│   └── gui/
│       └── main.py                    # UI MVP entry point
├── modules/
│   ├── documents/                     # Document lifecycle and metadata kernel
│   ├── signature/                     # Signature services and API
│   ├── usermanagement/                # Auth/session/user management
│   └── registry/                      # Derived registry projection
├── platform/
│   ├── runtime/                       # Container, bootstrap, lifecycle
│   ├── events/                        # Event bus/envelopes
│   ├── settings/                      # Settings registry/store/service
│   ├── licensing/                     # License guard/service/policy
│   └── logging/                       # Platform and audit logging
├── tests/                             # Unit, matrix, e2e CLI, UI smoke
├── docs/                              # Architecture and usage guides
└── storage/                           # Runtime data (settings, logs, DBs, artifacts)