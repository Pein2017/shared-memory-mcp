/** Ephemeral shared context only. No native-store writes or transcript loading.
 * A root startup may start the store-configured detached extraction through the CLI;
 * the CLI owns the enabled check and the extension never waits for it. */
import { execFile, spawn } from "node:child_process";
import { isAbsolute } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const bootstrapType = "shared-memory-context";
const taskType = "shared-memory-task-context";
const onboardingType = "shared-memory-onboarding";
const ownedTypes = new Set([bootstrapType, taskType, onboardingType]);
const byteLimit = 8000;
const maxChars = 6000;
const operations = new Set(["context", "capture", "approve", "supersede", "withdraw", "annotate", "dream_publish"]);
const toolPattern = /^(?:mcp__(?:shared_memory|shared-memory)__|(?:shared_memory|shared-memory)_)([a-z_]+)$/;
const servers = new Set(["shared-memory", "shared_memory"]);
type ToolIdentity = { toolName: string; details?: unknown };
function operationIdentity(value: ToolIdentity): { operation: string; valid: boolean } | null {
  const direct = toolPattern.exec(value.toolName)?.[1];
  const details = value.details as { server?: unknown; tool?: unknown; mode?: unknown } | undefined;
  if (direct && operations.has(direct)) {
    // Metadata may supplement a direct name but may not contradict it.
    return { operation: direct, valid: (details?.server === undefined || typeof details.server === "string" && servers.has(details.server))
      && (details?.tool === undefined || details.tool === direct) };
  }
  if (!["mcp", "mcp__shared_memory", "mcp__shared-memory"].includes(value.toolName)
      || typeof details?.server !== "string" || !servers.has(details.server)
      || typeof details.tool !== "string" || !operations.has(details.tool)
      || (details.mode !== undefined && details.mode !== "call")) return null;
  return { operation: details.tool, valid: true };
}
function failed(value: { isError?: boolean; details?: unknown }): boolean {
  const details = value.details as { error?: unknown; isError?: boolean } | undefined;
  return Boolean(value.isError || details?.isError || details?.error);
}
type Binding = { task_mode: "research" | "general" | null; query: string; current_status?: boolean };
type Packet = { status: string; packet_version?: number; packet_revision?: string; text: string;
  caller_context?: { cwd: string; harness: string; session_id: string; project_id: string; actor?: string };
  scope?: { cwd: string; project_id: string }; binding?: Binding; unchanged?: boolean;
  parts?: { kind: "bootstrap" | "task"; start: number; end: number; revision: string }[];
  part_offset_unit?: string; diagnostic?: { onboarding?: string }; continuation?: unknown };
type OwnedPart = { content: string; timestamp: number; customType: string };

function diagnostic(code: string): void {
  process.stderr.write(`${JSON.stringify({ shared_memory: "empty", diagnostic: code })}\n`);
}

function startExtraction(command: string, root: string): void {
  try {
    const child = spawn(command, ["--root", root, "extract", "--spawn"], { detached: true, stdio: "ignore" });
    child.on("error", () => diagnostic("extraction_not_started"));
    child.unref();
  } catch { diagnostic("extraction_not_started"); }
}

function runContext(command: string, args: string[]): Promise<Packet> {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: 15000, maxBuffer: 131072, encoding: "utf8" }, (error, stdout) => {
      try {
        const result = JSON.parse(stdout);
        if (error || !result || typeof result !== "object") throw new Error("context_command_failed");
        resolve(result);
      } catch { reject(new Error("invalid_context_output")); }
    });
  });
}

function packetFrom(content: unknown): Packet | null {
  if (!Array.isArray(content)) return null;
  const packets: Packet[] = [];
  for (const part of content) {
    if (part?.type !== "text" || typeof part.text !== "string") continue;
    try {
      const value = JSON.parse(part.text);
      if (value?.packet_version === 1) packets.push(value);
    } catch { /* Other tool text is not a shared packet. */ }
  }
  return packets.length === 1 ? packets[0] : null;
}

function isReceipt(content: unknown): boolean {
  if (!Array.isArray(content) || content.length !== 1 || content[0]?.type !== "text") return false;
  try {
    const value = JSON.parse(content[0].text);
    return value && typeof value.shared_memory_receipt === "string"
      && Object.keys(value).every(k => ["shared_memory_receipt", "delivery", "reason", "continuation"].includes(k))
      && (value.delivery === "current ephemeral packet; not another full copy"
          || value.reason === "context_call_failed_or_scope_mismatch" || value.reason === "context_budget")
      && !content[0].text.includes("<shared-memory-") && Buffer.byteLength(content[0].text) < 2048;
  } catch { return false; }
}

export interface SharedMemoryOptions { root?: string; cli?: string }

export function createSharedMemoryExtension(options: SharedMemoryOptions = {}) {
  return function sharedMemory(pi: ExtensionAPI): void {
    let parts: OwnedPart[] = [];
    let identity = "";
    let generation = 0;
    let binding: Binding = { task_mode: null, query: "" };
    let recoverBinding = false;
    let revision = "";
    const handled = new Set<string>();
    const failedCalls = new Set<string>();
    const key = (ctx: ExtensionContext) => JSON.stringify([ctx.cwd, ctx.sessionManager.getSessionId()]);
    const validIdentity = (packet: Packet, ctx: ExtensionContext) => packet?.packet_version === 1
      && isAbsolute(ctx.cwd) && Boolean(ctx.sessionManager.getSessionId()?.trim())
      && packet.caller_context?.cwd === ctx.cwd && packet.caller_context?.harness === "pi"
      && packet.caller_context?.session_id === ctx.sessionManager.getSessionId()
      && typeof packet.scope?.project_id === "string" && packet.scope.project_id.length > 0
      && packet.scope.cwd === ctx.cwd && packet.caller_context.project_id === packet.scope.project_id;
    function validateBinding(value: Binding | undefined): Binding {
      if (!value || ![null, "research", "general"].includes(value.task_mode)
          || typeof value.query !== "string" || value.query.length > 4096
          || (value.current_status !== undefined && typeof value.current_status !== "boolean"))
        throw new Error("invalid_task_binding");
      return { task_mode: value.task_mode, query: value.query,
        ...(value.current_status ? { current_status: true } : {}) };
    }
    function accept(packet: Packet, ctx: ExtensionContext, allowOnboarding = false): void {
      const old = parts;
      parts = [];
      const hint = packet?.diagnostic?.onboarding;
      if (allowOnboarding && ["unmapped", "ambiguous", "invalid"].includes(packet.status) && typeof hint === "string"
          && hint.startsWith("Shared-memory onboarding diagnostic:") && !hint.includes("<shared-memory-context>")
          && Array.from(hint).length <= maxChars && Buffer.byteLength(JSON.stringify(hint)) < byteLimit - 256) {
        parts = [{ content: hint, timestamp: Date.now(), customType: onboardingType }];
        return;
      }
      if (!validIdentity(packet, ctx) || packet.status !== "ok") throw new Error("invalid_context_scope_or_status");
      const nextBinding = validateBinding(packet.binding);
      if (typeof packet.packet_revision !== "string" || !packet.packet_revision
          || typeof packet.text !== "string" || Array.from(packet.text).length > maxChars
          || Buffer.byteLength(JSON.stringify(packet), "utf8") > byteLimit) throw new Error("context_budget");
      if (packet.unchanged) {
        if (!old.length || packet.text !== "" || revision !== packet.packet_revision
            || JSON.stringify(binding) !== JSON.stringify(nextBinding)) throw new Error("invalid_unchanged_context");
        parts = old; return;
      }
      const characters = Array.from(packet.text);
      const ranges = packet.parts;
      if (!ranges || packet.part_offset_unit !== "unicode-codepoints" || ranges.length < 1 || ranges.length > 2
          || ranges[0].kind !== "bootstrap" || ranges[0].start !== 0
          || ranges.at(-1)?.end !== characters.length) throw new Error("invalid_context_parts");
      const next: OwnedPart[] = [];
      let end = 0;
      for (const [index, range] of ranges.entries()) {
        if (!["bootstrap", "task"].includes(range.kind) || (index > 0 && range.kind !== "task")
            || !Number.isInteger(range.start) || !Number.isInteger(range.end)
            || range.start < end || range.end < range.start || range.end > characters.length
            || characters.slice(end, range.start).join("").trim()) throw new Error("invalid_context_parts");
        const customType = range.kind === "bootstrap" ? bootstrapType : taskType;
        const content = characters.slice(range.start, range.end).join("");
        const previous = old.find(p => p.customType === customType && p.content === content);
        next.push({ content, timestamp: previous?.timestamp ?? Date.now(), customType });
        end = range.end;
      }
      if (Buffer.byteLength(JSON.stringify(next.map(p => ({ role: "custom", ...p, display: false })))) > byteLimit)
        throw new Error("context_budget");
      binding = nextBinding;
      revision = packet.packet_revision;
      parts = next;
    }
    async function refresh(ctx: ExtensionContext, forceUnbound = false): Promise<void> {
      const current = ++generation;
      const old = parts;
      parts = [];
      if (identity !== key(ctx) || forceUnbound) { binding = { task_mode: null, query: "" }; revision = ""; handled.clear(); failedCalls.clear(); }
      identity = key(ctx);
      const root = options.root ?? process.env.SHARED_MEMORY_ROOT;
      const sessionId = ctx.sessionManager.getSessionId();
      if (!root || !isAbsolute(root) || !isAbsolute(ctx.cwd) || !sessionId?.trim()) {
        diagnostic("missing_or_invalid_context"); return;
      }
      try {
        const packet = await runContext(options.cli ?? process.env.SHARED_MEMORY_CLI ?? "shared-memory", [
          "--root", root, "context", "--cwd", ctx.cwd, "--harness", "pi", "--session-id", sessionId,
          "--actor", "pi", "--max-chars", String(maxChars), "--max-bytes", String(byteLimit),
          ...(binding.task_mode ? ["--task-mode", binding.task_mode] : []),
          ...(binding.query ? ["--query", binding.query] : []),
          ...(binding.current_status ? ["--current-status"] : []),
        ]);
        if (current === generation && identity === key(ctx)) { parts = old; accept(packet, ctx, true); }
      } catch (error) {
        if (current === generation) { parts = []; diagnostic(error instanceof Error ? error.message : "context_failed"); }
      }
    }
    pi.on("session_start", async (event, ctx) => {
      recoverBinding = true;
      await refresh(ctx);
      // Root startups only: Pi Web children and forks carry a parentSession header.
      const root = options.root ?? process.env.SHARED_MEMORY_ROOT;
      if (event.reason === "startup" && !ctx.sessionManager.getHeader()?.parentSession && root && isAbsolute(root))
        startExtraction(options.cli ?? process.env.SHARED_MEMORY_CLI ?? "shared-memory", root);
    });
    pi.on("session_compact", async (_event, ctx) => { recoverBinding = true; await refresh(ctx); });
    pi.on("tool_result", async (event, ctx) => {
      const operation = operationIdentity(event);
      if (!operation) return;
      if (identity !== key(ctx)) {
        binding = { task_mode: null, query: "" }; revision = ""; parts = []; handled.clear(); failedCalls.clear(); identity = key(ctx);
      }
      handled.add(event.toolCallId);
      if (handled.size > 2048) {
        const oldest = handled.values().next().value!;
        handled.delete(oldest); failedCalls.delete(oldest);
      }
      if (operation.operation === "context") {
        ++generation; // A foreground result supersedes any in-flight lifecycle refresh.
        recoverBinding = false;
        try {
          const packet = packetFrom(event.content);
          if (!operation.valid || failed(event) || !packet) throw new Error("context_call_failed");
          accept(packet, ctx);
          failedCalls.delete(event.toolCallId);
        } catch { parts = []; revision = ""; failedCalls.add(event.toolCallId); diagnostic("context_call_failed"); }
      } else if (operation.valid && !failed(event)) {
        await refresh(ctx);
      }
      // Native history retains the real tool output; the context projection below
      // substitutes only our model-visible duplicate, not the stored transcript.
    });
    pi.on("context", async (event, ctx) => {
      if (identity !== key(ctx)) { recoverBinding = true; await refresh(ctx, true); }
      if (recoverBinding) {
        recoverBinding = false;
        const calls = event.messages.filter(m => m.role === "toolResult" && operationIdentity(m)?.operation === "context" && !isReceipt(m.content));
        const last = calls.at(-1);
        if (last?.role === "toolResult") {
          const packet = packetFrom(last.content);
          // A latest failure is a fence: never recover an older successful binding.
          // Foreign-session history is redacted below, not adopted as this session's binding.
          if (!packet || validIdentity(packet, ctx) || failedCalls.has(last.toolCallId)) {
            try {
              if (!operationIdentity(last)?.valid || failed(last) || !packet || !validIdentity(packet, ctx) || packet.status !== "ok")
                throw new Error("context_call_failed");
              const freshParts = parts, freshBinding = binding, freshRevision = revision;
              accept(packet, ctx); // Validate budget, structure, scope and unchanged receipts too.
              if (JSON.stringify(binding) !== JSON.stringify(freshBinding)) await refresh(ctx);
              else { parts = freshParts; revision = freshRevision; }
            } catch { binding = { task_mode: null, query: "" }; revision = ""; parts = []; failedCalls.add(last.toolCallId); }
          }
          for (const message of calls) if (message.role === "toolResult") handled.add(message.toolCallId);
        }
      }
      const latestContext = event.messages.filter(m => m.role === "toolResult"
        && operationIdentity(m)?.operation === "context" && !isReceipt(m.content)).at(-1);
      const messages = [];
      for (const message of event.messages) {
        if (message.role === "custom" && ownedTypes.has(message.customType)) continue;
        if (message.role === "toolResult" && operationIdentity(message)?.operation === "context") {
          if (isReceipt(message.content)) { messages.push(message); continue; }
          const packet = packetFrom(message.content);
          let valid = !failedCalls.has(message.toolCallId) && operationIdentity(message)?.valid && !failed(message) && packet
            && validIdentity(packet, ctx) && packet.status === "ok";
          if (!handled.has(message.toolCallId)) {
            handled.add(message.toolCallId);
            try {
              // Eviction from the bounded receipt cache must not replay older bindings.
              if (message !== latestContext) throw new Error("historical_context_receipt");
              if (!packet || validIdentity(packet, ctx)) {
                if (!valid) throw new Error("context_call_failed");
                accept(packet!, ctx);
              }
            } catch {
              valid = false;
              if (message === latestContext) {
                parts = []; revision = ""; failedCalls.add(message.toolCallId); diagnostic("context_call_failed");
              }
            }
          }
          const continuation = packet && validIdentity(packet, ctx) && packet.status === "budget-limited"
            && operationIdentity(message)?.valid && !failed(message)
            && packet.continuation && typeof packet.continuation === "object"
            && !Array.isArray(packet.continuation)
            && Buffer.byteLength(JSON.stringify(packet), "utf8") <= byteLimit
            && Buffer.byteLength(JSON.stringify(packet.continuation), "utf8") <= 1024
            ? packet.continuation : undefined;
          // Redact every recognized context result, including malformed/failed output.
          // Native entries remain untouched; only this model-visible copy is replaced.
          messages.push({ ...message, content: [{ type: "text" as const,
            text: JSON.stringify(valid ? { shared_memory_receipt: packet!.packet_revision,
              delivery: "current ephemeral packet; not another full copy" }
              : { shared_memory_receipt: "unavailable", reason: continuation ? "context_budget" : "context_call_failed_or_scope_mismatch",
                  ...(continuation ? { continuation } : {}) }) }],
            structuredContent: undefined, details: undefined });
          continue;
        }
        messages.push(message);
      }
      let position = 0;
      while (messages[position]?.role === "system") position++;
      messages.splice(position, 0, ...parts.map(p => ({ role: "custom" as const, ...p, display: false })));
      return { messages };
    });
  };
}

export default createSharedMemoryExtension();
