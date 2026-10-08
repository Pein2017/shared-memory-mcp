## Purpose

Let an authorized agent identify and register the repository it is actually working in while preserving project isolation and actionable native diagnostics.

## ADDED Requirements

### Requirement: Read-only actionable project discovery
Project discovery and memory read operations SHALL identify actual cwd/Git bindings without registering projects or modifying knowledge. An unregistered independent Git repository SHALL expose a bounded reason and a valid existing registration invocation when unambiguous; unknown scope SHALL expose no project memory. Diagnostics SHALL NOT echo raw session inputs or credentials.

#### Scenario: Independent nested repository needs onboarding
- **WHEN** a caller works in an unregistered independent repository beneath a registered root
- **THEN** discovery identifies its own Git root and proposed registration, and memory recall remains empty until explicit registration

### Requirement: Caller-driven identity-preserving registration
An authorized agent SHALL be able to register its verified task repository through the existing explicit registration interface without a new per-project approval. Registered linked worktrees SHALL reuse the known Git identity. Name conflicts, ambiguous bindings and deliberately narrower subtree registrations SHALL NOT silently merge or broaden scopes. Registration SHALL NOT create sharing edges or change record sharing.

#### Scenario: Register and retry
- **WHEN** the agent executes the discovery-provided registration for an independent repository and retries using the resolved caller identity
- **THEN** the project resolves successfully with independent memory scope and unchanged sharing policy

#### Scenario: Linked worktree or restricted subtree
- **WHEN** discovery encounters a known common Git identity or an existing deliberate subtree-only binding
- **THEN** it reuses the permitted identity or explains the restriction without creating a broader binding

### Requirement: Native diagnostics retain onboarding information
Native adapters SHALL preserve a bounded actionable onboarding diagnostic at failed scope resolution while injecting no foreign project memory. Successful startup SHALL retain the established stable navigation behavior.

#### Scenario: Unregistered native startup
- **WHEN** a valid native session starts in an unregistered independent repository
- **THEN** the agent receives actionable project discovery guidance rather than only a generic unmapped code
