/** Recall only. Native stores and transcripts are never read or changed. */
import { execFile } from "node:child_process";
import { isAbsolute } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const customType = "shared-memory-context";
const onboardingType = "shared-memory-onboarding";
const maxChars = 6000;

function diagnostic(code: string): void {
  process.stderr.write(`${JSON.stringify({ shared_memory: "empty", diagnostic: code })}\n`);
}

function runContext(command: string, args: string[]): Promise<{ text: string; onboarding: boolean }> {
  return new Promise((resolve, reject) => {
    execFile(command, args, { timeout: 15000, maxBuffer: 131072, encoding: "utf8" },
      (error, stdout, stderr) => {
        if (error && !stdout) { reject(new Error("context_command_failed")); return; }
        // A successful command may have harmless runtime warnings on stderr.
        try {
          const result = JSON.parse(stdout);
          if (result.status !== "ok") {
            const hint = result.diagnostic?.onboarding;
            if (["unmapped", "ambiguous", "invalid"].includes(result.status)
                && typeof hint === "string" && hint.startsWith("Shared-memory onboarding diagnostic:")
                && Array.from(hint).length <= maxChars && !hint.includes("<shared-memory-context>")) {
              resolve({ text: hint, onboarding: true });
              return;
            }
            reject(new Error(["unmapped", "ambiguous", "invalid"].includes(result.status)
              ? result.status : "invalid_context_output"));
            return;
          }
          if (error) { reject(new Error("context_command_failed")); return; }
          if (typeof result.text !== "string" || Array.from(result.text).length > maxChars) {
            throw new Error("invalid_context_output");
          }
          resolve({ text: result.text, onboarding: false });
        } catch { reject(new Error("invalid_context_output")); }
      });
  });
}

export interface SharedMemoryOptions { root?: string; cli?: string }

/** A persistent wrapper can supply paths without depending on Pi's parent env. */
export function createSharedMemoryExtension(options: SharedMemoryOptions = {}) {
  return function sharedMemory(pi: ExtensionAPI): void {
  let text = "";
  let timestamp = 0;
  let identity = "";
  let generation = 0;
  let onboarding = false;
  const key = (ctx: ExtensionContext) => JSON.stringify([ctx.cwd, ctx.sessionManager.getSessionId()]);

  async function refresh(ctx: ExtensionContext): Promise<void> {
    const current = ++generation;
    text = "";
    onboarding = false;
    identity = key(ctx);
    const root = options.root ?? process.env.SHARED_MEMORY_ROOT;
    const sessionId = ctx.sessionManager.getSessionId();
    if (!root || !isAbsolute(root) || !isAbsolute(ctx.cwd) || !sessionId?.trim()) {
      diagnostic("missing_or_invalid_context");
      return;
    }
    try {
      const recalled = await runContext(options.cli ?? process.env.SHARED_MEMORY_CLI ?? "shared-memory", [
        "--root", root, "context", "--cwd", ctx.cwd, "--harness", "pi",
        "--session-id", sessionId, "--actor", "pi", "--max-chars", String(maxChars),
      ]);
      if (current === generation) { text = recalled.text; onboarding = recalled.onboarding; timestamp = Date.now(); identity = key(ctx); }
    } catch (error) {
      if (current === generation) diagnostic(error instanceof Error ? error.message : "context_failed");
    }
  }

  pi.on("session_start", async (_event, ctx) => { await refresh(ctx); });
  pi.on("session_compact", async (_event, ctx) => { await refresh(ctx); });
  pi.on("context", async (event, ctx) => {
    if (identity !== key(ctx)) await refresh(ctx);
    const messages = event.messages.filter((message) =>
      !(message.role === "custom" && [customType, onboardingType].includes(message.customType)));
    if (identity === key(ctx) && text) {
      // Keep unchanged recall ahead of ordinary growth, after any caller-owned prompt.
      let position = 0;
      while (messages[position]?.role === "system") position++;
      messages.splice(position, 0, { role: "custom", customType: onboarding ? onboardingType : customType,
        content: text, display: false, timestamp });
    }
    return { messages };
  });
  };
}

export default createSharedMemoryExtension();
