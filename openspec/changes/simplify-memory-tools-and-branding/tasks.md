## 1. Interface and branding

- [x] 1.1 Publish seven direct MCP names, clear reviewed lifecycle descriptions and packaged server/tool icon metadata; update current shared skill and probes, verified through SDK catalog/operation checks.
- [x] 1.2 Provide and validate self-contained SVG and skill UI metadata.

## 2. Auditable withdrawal

- [x] 2.1 Add validated append-only withdrawal markers, effective-status filtering and withdrawn-candidate rejection, verified by the withdrawal contract tests.
- [x] 2.2 Demonstrate pre-change failure and passing meaningful isolation, replay/recovery, concurrency, immutable history and stdio consumer checks.

## 3. Deployment and publication

- [x] 3.1 Validate package assets, existing owned three-harness registrations and offline native startup/tool discovery; reconcile only necessary installation changes.
- [ ] 3.2 Inspect publication contents, commit explicit owned paths, create the user-authorized public repository and push; verify remote revision and visibility.

## Acceptance evidence (2026-10-04)

- Package owner: pre-change withdrawal RED exit 1; final core/SDK/wheel suite exit 0, 91 passed. Pi adapter and skill checks exit 0. Logs remain under ignored `outputs/simplify-tools-{red,pytest,pi-adapters,skill}.log`.
- Lead installed editable 0.2.0 into the existing central environment without dependencies; all three owned registrations and the canonical skill link matched. No native configuration changes or duplicate registrations were needed. Existing MCP sessions must reconnect; icon rendering depends on the client.
- First offline native all-harness run: Pi/Claude passed; Codex startup view was present but the probe did not inherit its nested namespace. This original failure is retained at `outputs/native-startup-q1s0kjf4/selected-results.json`. Local namespace RED exit 1 and focused GREEN exit 0 (12 passed) establish the repair. A single Codex-only recheck passed at `outputs/native-startup-kxs4rpg8/selected-results.json`; unchanged Pi/Claude results are reused. Lead projection: `outputs/simplify-tools-native-acceptance.json`.
- Native Codex/Claude exit 1 is the deliberate local HTTP 400 rejection after serialization; probe acceptance confirms caller identity, current view and seven tool schemas. Pi verifies its installed SDK and real stdio MCP connection. Zero model inference or real provider calls.
- Original target files and native managed memories were not changed by qualification. Withdrawal remains a logical operation with historical visibility, not physical erasure or scientific validation.
