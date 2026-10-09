/** Ephemeral shared context only. No native-store writes or transcript loading. */
import { execFile } from "node:child_process";
import { isAbsolute } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const bootstrapType = "shared-memory-context";
const taskType = "shared-memory-task-context";
const onboardingType = "shared-memory-onboarding";
const ownedTypes = new Set([bootstrapType, taskType, onboardingType]);
const byteLimit = 8000;
const maxChars = 6000;
const toolPattern = /^mcp__(?:shared_memory|shared-memory)__(context|capture|approve|update|delete|curate|draft_publish)$/;
type Binding = { task_mode: "research" | "general" | null; query: string; current_status?: boolean };
type Packet = { status: string; packet_version?: number; packet_revision?: string; text: string;
  caller_context?: { cwd: string; harness: string; session_id: string; project_id: string };
  scope?: { cwd: string; project_id: string }; binding?: Binding; unchanged?: boolean;
  parts?: { kind: "bootstrap" | "task"; start: number; end: number; revision: string }[];
  part_offset_unit?: string; diagnostic?: { onboarding?: string } };
type OwnedPart = { content: string; timestamp: number; customType: string };

function diagnostic(code: string): void {
  process.stderr.write(`${JSON.stringify({ shared_memory: "empty", diagnostic: code })}\n`);
}

function runContext(command: string, args: string[]): Promise<Packet> {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: 15000, maxBuffer: 131072, encoding: "utf8" }, (error, stdout) => {
      try {
        const result = JSON.parse(stdout);
        if (error && result.status === "ok") throw new Error("context_command_failed");
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

export interface SharedMemoryOptions { root?: string; cli?: string }

export function createSharedMemoryExtension(options: SharedMemoryOptions = {}) {
  return function sharedMemory(pi: ExtensionAPI): void {
    let parts: OwnedPart[] = [];
    let identity = "";
    let generation = 0;
    let binding: Binding = { task_mode: null, query: "" };
    let recoverBinding = false;
    const handled = new Set<string>();
    const key = (ctx: ExtensionContext) => JSON.stringify([ctx.cwd, ctx.sessionManager.getSessionId()]);
    const validIdentity = (packet: Packet, ctx: ExtensionContext) => packet.packet_version === 1
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
    function accept(packet: Packet, ctx: ExtensionContext): void {
      const old = parts;
      parts = [];
      const hint = packet.diagnostic?.onboarding;
      if (["unmapped", "ambiguous", "invalid"].includes(packet.status) && typeof hint === "string"
          && hint.startsWith("Shared-memory onboarding diagnostic:") && !hint.includes("<shared-memory-context>")
          && Array.from(hint).length <= maxChars && Buffer.byteLength(JSON.stringify(hint)) < byteLimit - 256) {
        parts = [{ content: hint, timestamp: Date.now(), customType: onboardingType }];
        return;
      }
      if (!validIdentity(packet, ctx) || packet.status !== "ok") throw new Error("invalid_context_scope_or_status");
      binding = validateBinding(packet.binding);
      if (packet.unchanged) { parts = old; return; }
      if (typeof packet.text !== "string" || Array.from(packet.text).length > maxChars
          || Buffer.byteLength(JSON.stringify(packet), "utf8") > byteLimit) throw new Error("context_budget");
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
      parts = next;
    }
    async function refresh(ctx: ExtensionContext, forceUnbound = false): Promise<void> {
      const current = ++generation;
      const old = parts;
      parts = [];
      if (identity !== key(ctx) || forceUnbound) { binding = { task_mode: null, query: "" }; handled.clear(); }
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
        if (current === generation) { parts = old; accept(packet, ctx); }
      } catch (error) {
        if (current === generation) { parts = []; diagnostic(error instanceof Error ? error.message : "context_failed"); }
      }
    }
    pi.on("session_start", async (_event, ctx) => { recoverBinding = true; await refresh(ctx); });
    pi.on("session_compact", async (_event, ctx) => { recoverBinding = true; await refresh(ctx); });
    pi.on("tool_result", async (event, ctx) => {
      const operation = toolPattern.exec(event.toolName)?.[1];
      if (!operation) return;
      handled.add(event.toolCallId);
      if (handled.size > 2048) handled.delete(handled.values().next().value!);
      if (operation === "context") {
        try {
          const packet = packetFrom(event.content);
          if (event.isError || !packet) throw new Error("context_call_failed");
          accept(packet, ctx);
        } catch { parts = []; diagnostic("context_call_failed"); }
      } else if (!event.isError) {
        await refresh(ctx);
      }
      // Native history retains the real tool output; the context projection below
      // substitutes only our model-visible duplicate, not the stored transcript.
    });
    pi.on("context", async (event, ctx) => {
      if (identity !== key(ctx)) { recoverBinding = true; await refresh(ctx, true); }
      if (recoverBinding) {
        recoverBinding = false;
        const packets = event.messages.filter(m => m.role === "toolResult" && toolPattern.exec(m.toolName)?.[1] === "context")
          .map(m => ({ message: m, packet: packetFrom(m.content) })).filter(v => v.packet && validIdentity(v.packet, ctx));
        const last = packets.at(-1);
        if (last?.packet) {
          try {
            const recovered = validateBinding(last.packet.binding);
            if (JSON.stringify(recovered) !== JSON.stringify(binding)) { binding = recovered; await refresh(ctx); }
          } catch { binding = { task_mode: null, query: "" }; parts = []; }
          for (const value of packets) if (value.message.role === "toolResult") handled.add(value.message.toolCallId);
        }
      }
      const messages = [];
      for (const message of event.messages) {
        if (message.role === "custom" && ownedTypes.has(message.customType)) continue;
        if (message.role === "toolResult" && toolPattern.exec(message.toolName)?.[1] === "context") {
          const packet = packetFrom(message.content);
          if (packet && !validIdentity(packet, ctx)) {
            messages.push({ ...message, content: [{ type: "text" as const,
              text: JSON.stringify({ shared_memory_receipt: "unavailable", reason: "caller_scope_mismatch" }) }], structuredContent: undefined });
            continue;
          }
          if (packet && validIdentity(packet, ctx)) {
            if (!handled.has(message.toolCallId)) {
              handled.add(message.toolCallId);
              try { accept(packet, ctx); } catch { parts = []; diagnostic("context_call_failed"); }
            }
            messages.push({ ...message, content: [{ type: "text" as const,
              text: JSON.stringify({ shared_memory_receipt: packet.packet_revision, binding: packet.binding,
                                     delivery: "current ephemeral packet; not another full copy" }) }], structuredContent: undefined });
            continue;
          }
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
