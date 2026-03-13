import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { randomUUID } from "node:crypto";

import { execa } from "execa";

import type { JsonRpcRequest, RendererEvent, WorkflowParams } from "./types.js";

const thisFile = fileURLToPath(import.meta.url);
const srcDir = path.dirname(thisFile);
const projectRoot = path.resolve(srcDir, "..");
const ipcServerPath = path.join(projectRoot, "core_engine", "ipc_server.py");

class RequestExecutionError extends Error {
  readonly alreadyReported: boolean;

  constructor(message: string, alreadyReported: boolean) {
    super(message);
    this.name = "RequestExecutionError";
    this.alreadyReported = alreadyReported;
  }
}

function normalizeEvent(line: string): RendererEvent | null {
  if (!line.trim()) {
    return null;
  }

  try {
    const parsed = JSON.parse(line) as Record<string, unknown>;

    if (typeof parsed.event === "string") {
      return {
        event: parsed.event as RendererEvent["event"],
        message: typeof parsed.message === "string" ? parsed.message : undefined,
        target: typeof parsed.target === "string" ? parsed.target : undefined,
        result: typeof parsed.result === "string" ? parsed.result : undefined,
      };
    }

    if (parsed.jsonrpc === "2.0" && typeof parsed.method === "string" && parsed.params) {
      const params = parsed.params as Record<string, unknown>;

      if (parsed.method === "stream_status") {
        const status = typeof params.status === "string" ? params.status : "info";

        return {
          event: status === "planning" ? "planning" : status === "review" ? "review" : "info",
          message: typeof params.msg === "string" ? params.msg : undefined,
          target: typeof params.target === "string" ? params.target : undefined,
        };
      }

      if (parsed.method === "stream_log") {
        return {
          event: "sub_agent_log",
          message: typeof params.chunk === "string" ? params.chunk : undefined,
          target: typeof params.agent === "string" ? params.agent : undefined,
        };
      }
    }

    if (parsed.jsonrpc === "2.0" && parsed.result) {
      const result = parsed.result as Record<string, unknown>;

      return {
        event: result.success === false ? "error" : "done",
        message: typeof result.message === "string" ? result.message : undefined,
        result: typeof result.message === "string" ? result.message : undefined,
      };
    }

    if (parsed.jsonrpc === "2.0" && parsed.error) {
      return null;
    }
  } catch {
    return {
      event: "sub_agent_log",
      message: line,
    };
  }

  return null;
}

function buildRequest(
  method: string,
  params: WorkflowParams,
): JsonRpcRequest<Record<string, unknown>> {
  return {
    jsonrpc: "2.0",
    method,
    id: params.sessionId ?? randomUUID(),
    params: {
      session_id: params.sessionId,
      prompt: params.prompt,
      working_dir: params.workingDir,
      yolo: params.yolo ?? false,
    },
  };
}

async function executeRequest(
  method: string,
  params: WorkflowParams,
  onEvent: (event: RendererEvent) => void,
): Promise<string> {
  const pythonBin = process.env.OMNICODE_PYTHON_BIN ?? "python3";
  const child = execa(pythonBin, ["-u", ipcServerPath], {
    cwd: projectRoot,
    reject: false,
    stdin: "pipe",
    stdout: "pipe",
    stderr: "pipe",
  });

  let finalMessage = "";

  const stdoutInterface = createInterface({
    input: child.stdout!,
    crlfDelay: Infinity,
  });
  const stderrInterface = createInterface({
    input: child.stderr!,
    crlfDelay: Infinity,
  });

  stdoutInterface.on("line", (line) => {
    const event = normalizeEvent(line);
    if (!event) {
      return;
    }

    if (event.event === "done" || event.event === "error") {
      finalMessage = event.result ?? event.message ?? finalMessage;
    }

    onEvent(event);
  });

  stderrInterface.on("line", (line) => {
    onEvent({
      event: "sub_agent_log",
      target: "python",
      message: line,
    });
  });

  const request = buildRequest(method, params);
  child.stdin!.write(`${JSON.stringify(request)}\n`);
  child.stdin!.end();

  const result = await child;

  stdoutInterface.close();
  stderrInterface.close();

  if (result.exitCode !== 0) {
    const fallbackMessage = finalMessage || result.stderr || `Python engine exited with ${result.exitCode}`;
    throw new RequestExecutionError(fallbackMessage, Boolean(finalMessage));
  }

  return finalMessage || "Workflow complete";
}

export function runWorkflow(
  params: WorkflowParams,
  onEvent: (event: RendererEvent) => void,
): Promise<string> {
  return executeRequest("run_workflow", params, onEvent);
}

export function resumeWorkflow(
  params: WorkflowParams,
  onEvent: (event: RendererEvent) => void,
): Promise<string> {
  return executeRequest("resume_workflow", params, onEvent);
}
