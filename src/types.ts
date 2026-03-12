export interface WorkflowParams {
  prompt: string;
  workingDir: string;
  sessionId?: string;
  yolo?: boolean;
}

export interface RendererEvent {
  event: "planning" | "dispatch" | "sub_agent_log" | "review" | "done" | "error" | "info";
  message?: string;
  target?: string;
  result?: string;
}

export interface JsonRpcRequest<TParams> {
  jsonrpc: "2.0";
  method: string;
  params: TParams;
  id: string;
}
