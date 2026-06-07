// 与 Python 端 rpc_types.py 协议保持一致

export type RpcRequest = {
  type: "request";
  id: number;
  method: string;
  params: Record<string, unknown>;
};

export type RpcResponse = {
  type: "response";
  id: number;
  result: unknown;
};

export type RpcEventMessage = {
  type: "event";
  event: string;
  data: unknown;
};

export type RpcErrorMessage = {
  type: "error";
  id: number;
  error: { code: string; message: string; detail: unknown };
};

export type RpcMessage = RpcRequest | RpcResponse | RpcEventMessage | RpcErrorMessage;

// ===== 业务事件 data 形状 =====

export type ReadyData = {
  version: string;
  python_version: string;
  uv_lock_hash: string;
};

export type ScreenshotData = {
  step: number;
  page_state: string;
  image_b64: string;
  width: number;
  height: number;
};

export type StepStartedData = {
  step: number;
  page_state: string;
};

export type StepCompletedData = {
  step: number;
  question: string;
  options: { key: string; text: string }[];
  answer: string[];
  confidence: number;
  page_changed: boolean;
  screenshot_b64?: string;
};

export type PausedData = {
  step: number;
  reason: string;
  screenshot_b64: string;
};

export type LogData = {
  level: "INFO" | "WARN" | "ERROR" | "DEBUG";
  message: string;
  ts: string;
};

export type ConfigChangedData = {
  new_config: Record<string, unknown>;
  hot_fields: string[];
};

export type CrashedData = {
  exit_code: number;
  stderr_tail: string;
};

export type StoppedData = {
  reason: string;
  total_steps: number;
};

export type CalibrationChangedData = {
  target: {
    hwnd: number;
    pid: number;
    title: string;
    process_name: string;
  } | null;
  client_rect: number[] | null;
  phone_viewport_in_client: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  phone_viewport_ratio: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
};

// ===== 业务方法返回形状 =====

export type WindowInfo = {
  hwnd: number;
  pid: number;
  title: string;
  rect: number[];
};

export type CalibrationState = {
  target: {
    hwnd: number;
    pid: number;
    title: string;
    process_name: string;
  } | null;
  client_rect: number[] | null;
  phone_viewport_in_client: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  phone_viewport_ratio: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  last_capture_b64: string | null;
};

export type SessionSummary = {
  session_id: string;
  started_at: string;
  step_count: number;
  stop_reason: string;
};