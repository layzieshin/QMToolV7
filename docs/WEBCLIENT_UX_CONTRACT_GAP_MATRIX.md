# Webclient UX Contract Gap Matrix

Status: Active transition detail (P1)

Canonical UX: `docs/WEBCLIENT_UX_SPECIFICATION.md`
Transition steering: `docs/AP-029_WEB_POSTGRES_TRANSITION_PLAN.md`
Baseline: `main` @ `58caddac224ab46ed63392fba92fc11b94e9ddf2`

## Purpose and authority

This document records changing implementation evidence, contract gaps, deferred target patterns,
and the disposition of the historical Webclient package. It is not a second source of truth for
product UX. P0 architecture and `docs/WEBCLIENT_UX_SPECIFICATION.md` win on binding boundaries and
interaction decisions; AP-029 owns checkpoint order.

The external handoff and its historical schemas are reconstruction evidence only. They do not
authorize code, OpenAPI, persistence, business rules, deployment technology, or WEB01 scope.

## Status vocabulary

- `Already Supported`: a current authoritative contract is sufficient; WEB01 still needs its UI adapter.
- `UX-only / WEB01`: the behavior can be implemented without adding a backend or business contract.
- `Backend Contract Required Before WEB01`: WCON00 must close the gap before INT00/WEB01.
- `OPS00/INT00 Relevant`: the concern belongs to operations or integration readiness, not UX00.
- `Deferred`: target direction only; not a current WEB01 requirement.

## Current contract gaps

| ID | Area | Current evidence on baseline | Classification | Owner / consequence |
| --- | --- | --- | --- | --- |
| GAP-01 | Allowed Actions / Action Metadata | Documents exposes server-computed `available_actions`; generic labels, severity, confirmation and reason metadata are absent | Backend Contract Required Before WEB01 | WCON00 defines descriptors and the `allowed_actions`/`available_actions` boundary; the client never derives permissions |
| GAP-02 | ETag / Conflict Handling | Documents mutations use ETag/If-Match with 428 and structured 409 conflicts | Already Supported | WEB01 renders the conflict UX; no replacement concurrency rule |
| GAP-03 | Preferences | No server preference contract | UX-only / WEB01 | Only non-sensitive, namespaced local comfort settings; server sync remains deferred |
| GAP-04 | Saved Views | No persisted view contract | Deferred | URL/local personal view may be UX-only; shared/server views are not WEB01 scope |
| GAP-05 | Signature Presets | User/global templates exist; `show_time`, document type/role context and last-matching suggestion are absent | Backend Contract Required Before WEB01 | WCON00 closes only the fields made binding by the P0 signature UX |
| GAP-06 | Edit Locks | No lease/lock contract | Deferred | ETag remains mandatory; no fake lock |
| GAP-07 | Tasks | Documents home tasks and review actions exist | Already Supported | WEB01 may render Documents tasks; cross-module inbox remains deferred |
| GAP-08 | Notifications | No persistent notification service; P0 excludes it from the first pilot | Deferred | Do not simulate or block WEB01 |
| GAP-09 | Jobs | No generic authoritative job/progress service | OPS00/INT00 Relevant | Deferred for WEB01 unless an explicitly approved pilot flow becomes asynchronous |
| GAP-10 | Attachments | Documents artifacts/uploads/content streaming exist | Already Supported | DMS component may use them; generic cross-module attachments remain deferred |
| GAP-11 | Object Picker | User directory can support a user picker; no generic object picker | UX-only / WEB01 | User picker may adapt the directory; generic relation picker remains deferred |
| GAP-12 | Controlled Download | Artifact content exists but preview, download and entitlement semantics are not separated | Backend Contract Required Before WEB01 | WCON00 defines an explicit server-authorized download action and preview distinction |
| GAP-13 | Controlled Print / IPP | No canonical print adapter or HTTP contract | OPS00/INT00 Relevant | Deferred unless separately promoted; no silent OPS00 expansion |
| GAP-14 | Global Search | No cross-module search contract | Deferred | WEB01 must not fan out over all module endpoints; Documents list query is GAP-19 |
| GAP-15 | Audit / History | Append-only audit write path exists; no WEB01-suitable read contract | Backend Contract Required Before WEB01 | WCON00 defines the bounded read model without exposing technical logs |
| GAP-16 | Connection State | WEB00 shell probes unversioned `/health`; AP-029 D05 requires browser traffic on `/api/v1` | Backend Contract Required Before WEB01 | WCON00 owns a versioned Same-Origin `/api/v1` browser connection/readiness contract. Existing root `/health` remains an OPS/readiness probe, not a valid WEB01 browser contract. WEB01 banner/retry/write-blocking still requires that WCON00 contract; maintenance/readiness stays OPS00/INT00 relevant |
| GAP-17 | Reauthentication | Password verification and signature reauthentication exist | Already Supported | WEB01 owns the focused UI flow; credentials are never persisted |
| GAP-18 | UI Bootstrap / Module Manifest | No central module/capability bootstrap contract | Backend Contract Required Before WEB01 | WCON00 defines the minimum manifest; no per-module frontend bundle |
| GAP-19 | Documents List Query / Pagination / Filter / Sort | Pool reads exist but no canonical paged query contract for the specified list UX | Backend Contract Required Before WEB01 | WCON00 defines server-side list semantics |
| GAP-20 | Structured Field Errors | No stable fachlich named `field_errors` envelope for generic forms | Backend Contract Required Before WEB01 | WCON00 defines a transport-only error representation; services remain authoritative |
| GAP-21 | PDF Inline Preview | Current artifact content uses download/attachment semantics | Backend Contract Required Before WEB01 | WCON00 separates inline preview from controlled download |

## WCON00 boundary

WCON00 is a narrow technical contract-completion checkpoint after OPS00 and before INT00. It owns
only GAP-01, GAP-05, GAP-12, GAP-15, GAP-16, GAP-18, GAP-19, GAP-20 and GAP-21. Its implementation must use
the existing module public APIs and thin `/api/v1` transport; it must not move business logic into
the backend host or browser.

Notifications, generic jobs, global search, edit locks, IPP and generic cross-module attachments
are not silently included. Promoting one requires a later explicit steering decision.

## Historical decision disposition

Every decision from the 2026-08-16 historical decision log appears exactly once below. `CURRENT`
means confirmed by current canonical architecture or implementation. `MISSING_FROM_CANONICAL_DOCS`
means UX00 incorporates the stable UX direction or marks it deferred; it does not make the item a
WEB01 requirement. `REFERENCE_ONLY` is retained for later owner decisions. `SUPERSEDED` records a
historical rule replaced by newer governance.

| ID | Historical decision | Disposition | Current treatment |
| --- | --- | --- | --- |
| D01 | Vue 3 + TypeScript + Vite SPA | CURRENT | AP-029/WEB00 stack |
| D02 | Vuetify behind QM components | CURRENT | P0 component boundary |
| D03 | Generic/metadata-driven by default | CURRENT | AP-029 generic-first |
| D04 | Modules deliver no client bundle | CURRENT | Central SPA invariant |
| D05 | Slim dashboard | MISSING_FROM_CANONICAL_DOCS | Canonicalized as stable UX |
| D06 | Limited dashboard personalization | MISSING_FROM_CANONICAL_DOCS | Strong default; personal preference only |
| D07 | Split View preferred, not mandatory | MISSING_FROM_CANONICAL_DOCS | Canonicalized pattern |
| D08 | Read mode before explicit edit | MISSING_FROM_CANONICAL_DOCS | Canonicalized pattern |
| D09 | Module navigation plus contextual navigation | MISSING_FROM_CANONICAL_DOCS | Canonicalized shell pattern |
| D10 | Desktop first; mobile later | MISSING_FROM_CANONICAL_DOCS | Canonicalized, selective mobile deferred |
| D11 | No offline sync | MISSING_FROM_CANONICAL_DOCS | No mutation queue or fake offline mode |
| D12 | i18n-ready, German first | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D13 | Light theme and central tokens | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D14 | Explicit fachlich save; preference autosave | MISSING_FROM_CANONICAL_DOCS | Canonicalized with local-data limits |
| D15 | Unsaved-change warning | MISSING_FROM_CANONICAL_DOCS | Canonicalized dirty-state rule |
| D16 | Global search plus module filters | MISSING_FROM_CANONICAL_DOCS | Module filtering direction retained; global search deferred |
| D17 | Central tasks/inbox | MISSING_FROM_CANONICAL_DOCS | Documents tasks supported; cross-module inbox deferred |
| D18 | Backend determines allowed actions | CURRENT | Service authority; GAP-01 metadata remains |
| D19 | User table personalization over admin default | MISSING_FROM_CANONICAL_DOCS | Canonicalized personal UI preference |
| D20 | Stable URLs and URL list state | MISSING_FROM_CANONICAL_DOCS | Canonicalized routing rule |
| D21 | Inline document viewing | CURRENT | AP-029 WEB01 pilot requirement |
| D22 | Controlled download deny-by-default | MISSING_FROM_CANONICAL_DOCS | Canonical UX; GAP-12 blocks WEB01 |
| D23 | Backend-controlled printer selection | REFERENCE_ONLY | OPS/print decision deferred |
| D24 | Print copies and optional purpose/recipient | REFERENCE_ONLY | OPS/controlled-copy decision deferred |
| D25 | Unique copy ID per physical copy | REFERENCE_ONLY | Later compliance/print decision |
| D26 | DocuSeal-like placement with QM flexibility | MISSING_FROM_CANONICAL_DOCS | Pattern only; no clone/envelope scope |
| D27 | Personal signature presets by type/role | MISSING_FROM_CANONICAL_DOCS | Canonical UX; GAP-05 |
| D28 | Focused dialogs for critical actions | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D29 | Backend-driven module discovery | MISSING_FROM_CANONICAL_DOCS | GAP-18 WCON00 |
| D30 | Central settings/admin shell | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D31 | Personal settings separated from administration | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D32 | Hide unauthorized/unlicensed modules | MISSING_FROM_CANONICAL_DOCS | Server capabilities only; GAP-18 |
| D33 | Central severity-based feedback | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D34 | Browser tabs, not app tabs | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D35 | Clear tabs for complex detail | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D36 | Fachlich history separated from technical log | CURRENT | AP-029 audit boundary |
| D37 | Normal users see only fachlich history | MISSING_FROM_CANONICAL_DOCS | Canonical UX; GAP-15 read contract |
| D38 | Mandatory hard edit lease | SUPERSEDED | Optional/deferred; ETag is mandatory |
| D39 | Admin unlocks only stale/orphaned leases | SUPERSEDED | Applies only if a later lock service is approved |
| D40 | Delete/archive in overflow with confirmation | MISSING_FROM_CANONICAL_DOCS | Canonicalized action placement |
| D41 | Reason requirement comes from action rule | MISSING_FROM_CANONICAL_DOCS | GAP-01 action metadata |
| D42 | Server-side pagination by default | MISSING_FROM_CANONICAL_DOCS | GAP-19 WCON00 |
| D43 | Central pragmatic accessibility | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D44 | Forms by default; wizard for complexity | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D45 | Draft optional | MISSING_FROM_CANONICAL_DOCS | No general draft contract invented |
| D46 | Changed-field markers when economical | MISSING_FROM_CANONICAL_DOCS | Optional UX only |
| D47 | Personal and optional shared saved views | MISSING_FROM_CANONICAL_DOCS | Personal local optional; shared deferred |
| D48 | Dashboard default with later personal start | MISSING_FROM_CANONICAL_DOCS | Canonicalized, local preference bounded |
| D49 | Bulk actions opt-in | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D50 | Personal favorites | MISSING_FROM_CANONICAL_DOCS | Optional/deferred navigation aid |
| D51 | Configurable idle timeout and warning | REFERENCE_ONLY | Security/session owner decision |
| D52 | Edge, Chrome and Firefox support matrix | REFERENCE_ONLY | Pilot/support decision, not UX00 |
| D53 | User density with compact default | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D54 | Central job/progress mechanism | MISSING_FROM_CANONICAL_DOCS | Target retained but deferred; GAP-09 |
| D55 | Subtle central job overview | MISSING_FROM_CANONICAL_DOCS | Deferred with GAP-09 |
| D56 | Persistent notification center as V1 | SUPERSEDED | P0 excludes notification service from first pilot |
| D57 | Notification acknowledgement rules as V1 | SUPERSEDED | Future notification contract only |
| D58 | Central attachment mechanism | MISSING_FROM_CANONICAL_DOCS | DMS artifacts current; generic future deferred |
| D59 | Central object/relation picker | MISSING_FROM_CANONICAL_DOCS | User picker possible; generic future deferred |
| D60 | Staged validation, backend authoritative | CURRENT | Service/API boundary |
| D61 | Metadata-driven contextual help | MISSING_FROM_CANONICAL_DOCS | Prepared UX, contract-dependent |
| D62 | Small universal shortcuts | MISSING_FROM_CANONICAL_DOCS | Optional UX |
| D63 | Standard action positions | MISSING_FROM_CANONICAL_DOCS | Canonicalized |
| D64 | SSO/OIDC separate backend topic | REFERENCE_ONLY | Local login remains; future security package |
| D65 | Breadcrumbs for hierarchy | MISSING_FROM_CANONICAL_DOCS | Canonicalized conditional pattern |
| D66 | Slim command palette | MISSING_FROM_CANONICAL_DOCS | Navigation aid; global search deferred |
| D67 | Personal recent/last view | MISSING_FROM_CANONICAL_DOCS | Optional local preference; server sync deferred |
| D68 | Global plus module create action | MISSING_FROM_CANONICAL_DOCS | Requires server actions; no invented creation rights |
| D69 | Context menu as extra desktop comfort | MISSING_FROM_CANONICAL_DOCS | Optional duplicate, never sole path |
| D70 | Polling first, SSE later | REFERENCE_ONLY | Implementation choice per contract/integration |
| D71 | Central export mechanism, module opt-in | MISSING_FROM_CANONICAL_DOCS | AP-029 export categories win; OPS-owned |
| D72 | Isolate module UI errors | MISSING_FROM_CANONICAL_DOCS | Canonical shell resilience |
| D73 | Admin module/system status view | MISSING_FROM_CANONICAL_DOCS | OPS/readiness dependent |
| D74 | Local state contains no persistent fachlich copy | CURRENT | P0 client-data boundary |
| D75 | Connection banner and retry | CURRENT | WEB00 connection state |
| D76 | Central contract versioning | CURRENT | `/api/v1`/OpenAPI governance |
| D77 | Clear contract errors with admin detail | MISSING_FROM_CANONICAL_DOCS | GAP-20 plus safe diagnostics |
| D78 | Contextual permission masking | MISSING_FROM_CANONICAL_DOCS | Server error/visibility contract; no client inference |
| D79 | Never silently overwrite stale edit data | CURRENT | ETag conflict invariant |
| D80 | Cross-module personal activity | MISSING_FROM_CANONICAL_DOCS | Explicitly deferred |
| D81 | Integrated Caddy as fixed deployment | REFERENCE_ONLY | OPS00 decides deployment mechanics |
| D82 | Same-Origin HTTPS | CURRENT | AP-029 D05 |
| D83 | Local-CA onboarding by QR/download | REFERENCE_ONLY | OPS/security decision |
| D84 | Hostname/DNS rule after field test | REFERENCE_ONLY | OPS/pilot decision |
| D85 | HttpOnly cookie session; bearer for CLI/API | CURRENT | AP-029 browser contract |
| D86 | IPP as first print adapter | REFERENCE_ONLY | OPS/print decision deferred |
| D87 | Signature time toggle on date line | MISSING_FROM_CANONICAL_DOCS | Canonical UX; GAP-05 |
| D88 | Webclient is GUI source of truth | CURRENT | P0 GUI source |
| D89 | PostgreSQL-only product persistence | CURRENT | P0 database policy |
| D90 | Bundled PostgreSQL/Caddy may be hidden | REFERENCE_ONLY | Installer/licensing/OPS decision |
| D91 | Prefer permissive runtime licenses | REFERENCE_ONLY | Existing licensing review remains authoritative |
| D92 | Integrate container prototype early | SUPERSEDED | AP-029 CB00/CB01 order replaces it |

## Review rule

WEB01 is not ready merely because this matrix exists. It becomes eligible only after OPS00 and
WCON00 are PASS and INT00 verifies the combined contracts. Any change that promotes a deferred
item or changes the P0 interaction model requires normal AP-029 steering and review; this P1 file
cannot do so alone.
