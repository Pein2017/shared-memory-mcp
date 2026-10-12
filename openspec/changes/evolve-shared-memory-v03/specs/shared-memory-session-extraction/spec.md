## Purpose

Turn idle native session transcripts into source-linked, non-recalled candidate memories through a bounded startup-triggered cheap-model extraction, so that manual Dreaming consolidates pre-digested candidates instead of reading raw history from scratch.

## ADDED Requirements

### Requirement: Startup-triggered bounded extraction

Extraction SHALL be started only by a root-session startup of a supported harness or by an explicit operator CLI invocation, never by a daemon, timer or per-turn hook. One startup SHALL claim at most two sessions that have been idle for at least one hour, are not older than the configured age window, and have not been successfully extracted at their current size. Claims SHALL be leased in the store's coordination database so that concurrent startups across harnesses cannot extract the same session twice; a failed claim SHALL be retried later with backoff. The extraction process SHALL run detached from the hook and SHALL NOT delay hook output.

#### Scenario: Two harnesses start at once
- **WHEN** a Codex startup and a Claude startup both find the same idle session eligible
- **THEN** exactly one claims it, the other claims a different session or nothing, and the session is extracted once

#### Scenario: Session still active
- **WHEN** a session's transcript was modified within the last hour
- **THEN** it is not claimed

#### Scenario: Extraction disabled
- **WHEN** extraction is not enabled in the store configuration
- **THEN** startup performs recall only and no extraction process is started

### Requirement: Original transcripts as primary input

Extraction SHALL read the session through the same public-projection readers used by Dreaming, so that private payloads, compaction summaries and credential files are excluded and native memory stores are never written. The model input SHALL be the public message text with tool noise removed, bounded in size; sessions exceeding the bound SHALL be extracted in bounded windows with the window recorded. Native Codex and Claude memory directories MAY be registered as read-only document sources for Dreaming but SHALL NOT be extraction inputs or outputs.

#### Scenario: Large Pi session
- **WHEN** an eligible session exceeds the input bound
- **THEN** extraction processes bounded windows in order, records each window's event range, and resumes from the last completed window after interruption

#### Scenario: Native memory untouched
- **WHEN** extraction runs on a host with Codex and Claude native memories
- **THEN** no file under either native memory directory is created, modified or removed

### Requirement: Candidates with lineage, outside default recall

Each extraction SHALL call the configured cheap model once per window with a fixed structured-output contract and SHALL write the result only as candidates through the ordinary capture path with `assurance: model-extracted`. Each candidate SHALL carry the session transcript path, event range, harness, model used for extraction and, for subagent sessions, the agent identifier, parent session, role, model and effort of that worker when known. A no-output result SHALL be recorded as a completed extraction without a candidate. Extraction candidates SHALL NOT enter default recall or startup context, SHALL appear in search with explicit statuses and in Dreaming's default inventory, and SHALL follow the seven-day stale rule of shared-memory-core.

#### Scenario: Root session yields a lesson
- **WHEN** an idle root session is extracted
- **THEN** zero or more candidates exist with that transcript's path and event range as sources, none of them appears in the next startup packet, and a status search for `model-extracted` lists them

#### Scenario: Worker session is classified, not excluded
- **WHEN** an idle subagent session is extracted
- **THEN** its candidates are tagged as worker-derived with the worker's harness, model, role and parent session, and the extraction prompt asks for task, mistakes and their likely cause rather than project knowledge

#### Scenario: Secret in transcript
- **WHEN** the public text contains a secret-like pattern
- **THEN** the pattern is redacted before the model call and any candidate carries a `secret_pattern` notice

### Requirement: Model selection and cost bounds

The extraction model SHALL be configured explicitly per store from the harness-native cheap models available on the host; no default paid model SHALL be assumed. Each extraction SHALL record the model, token usage when reported, and wall time in the store's extraction journal. A provider, quota or authentication failure SHALL stop that extraction, release its lease with backoff, and MUST NOT fall back to another model.

#### Scenario: No model configured
- **WHEN** extraction is enabled but no model is configured
- **THEN** startup reports the missing configuration once in its diagnostic and starts no extraction

#### Scenario: Quota failure
- **WHEN** the configured model returns a quota error
- **THEN** the session's lease is released with backoff, the journal records the failure, and no other model is tried

### Requirement: Operator visibility and replay

The operator CLI SHALL list extraction state per session (eligible, leased, extracted, failed, no-output) with the journal entries, SHALL allow explicit extraction of a named transcript, and SHALL allow re-extraction of a session only by explicit request. Repeating an extraction for an unchanged transcript and window SHALL replay the existing candidates rather than creating duplicates.

#### Scenario: Explicit extraction of one transcript
- **WHEN** the operator extracts a named transcript that was already extracted at the same size
- **THEN** the existing candidates are reported and no duplicate is created unless re-extraction is explicitly requested
