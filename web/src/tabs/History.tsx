import { useEffect, useState } from "react";
import { api } from "../lib/tauri-bridge";
import type { SessionSummary } from "../lib/types";
import { useAppStore } from "../lib/store";

type TraceStep = {
  step?: number;
  timestamp?: string;
  question_type?: string;
  question?: string;
  solver_answer?: string[];
  answer?: string[];
  solver_confidence?: number;
  confidence?: number;
  error?: string | null;
};

type SessionDetailData = {
  session_id: string;
  steps: TraceStep[];
};

type SessionListResponse = SessionSummary[] | { sessions?: SessionSummary[] };

function normalizeSessions(data: SessionListResponse): SessionSummary[] {
  return Array.isArray(data) ? data : data.sessions ?? [];
}

function relativeTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (isNaN(t)) return iso;
  const diff = Date.now() - t;
  const day = 24 * 60 * 60 * 1000;
  const d = new Date(iso);
  const time = `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  if (diff < day) return `今天 ${time}`;
  if (diff < 2 * day) return `昨天 ${time}`;
  if (diff < 7 * day) return `${Math.floor(diff / day)} 天前`;
  return iso.slice(0, 10);
}

function stopReasonColor(reason: string | null): "ok" | "err" | "warn" | "info" {
  if (reason === "submit_detected" || reason === "max_steps_reached") return "ok";
  if (reason === "user_quit" || reason === "running") return "info";
  if (reason === "consecutive_errors" || reason === "fatal") return "err";
  return "warn";
}

function questionTypeLabel(type?: string): string {
  if (type === "single" || type === "single_choice") return "单选";
  if (type === "multi" || type === "multi_choice") return "多选";
  if (type === "judge" || type === "judgement") return "判断";
  if (type === "skip" || type === "unknown") return "跳过";
  return type || "未知";
}

function excerpt(text?: string): string {
  if (!text) return "无题干";
  return text.length > 72 ? `${text.slice(0, 72)}…` : text;
}

function stepAnswer(step: TraceStep): string {
  const answer = step.solver_answer ?? step.answer ?? [];
  return answer.length > 0 ? answer.join("、") : "无";
}

function stepConfidence(step: TraceStep): number | null {
  return step.solver_confidence ?? step.confidence ?? null;
}

export function History() {
  const { sessions, setSessions } = useAppStore();
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    api.listTraceSessions(50)
      .then((data) => {
        const list = normalizeSessions(data as SessionListResponse);
        setSessions(list);
        if (list.length > 0 && !active) setActive(list[0].session_id);
      })
      .catch((e) => console.error("listTraceSessions failed", e));
  }, [setSessions, active]);

  const activeSession = sessions.find((s) => s.session_id === active);

  return (
    <div className="flex flex-col h-full">
      <div className="px-8 pt-8 max-w-[1200px] w-full mx-auto">
        <div className="text-[22px] font-semibold tracking-tight mb-1">历史</div>
        <div className="text-[13px] text-muted mb-6">过往 session 列表与步骤详情</div>
      </div>
      <div className="flex-1 grid grid-cols-[320px_1fr] border-t border-line" style={{ minHeight: 0 }}>
        <div className="overflow-auto bg-surface1 border-r border-line">
          {sessions.length === 0 ? (
            <div className="p-6 text-dim text-[13px]">暂无 session 记录</div>
          ) : (
            sessions.map((s) => {
              const isActive = s.session_id === active;
              const color = stopReasonColor(s.stop_reason);
              return (
                <button
                  key={s.session_id}
                  onClick={() => setActive(s.session_id)}
                  className={`w-full text-left p-3 px-4 border-b border-line transition-colors active:-translate-y-px ${
                    isActive ? "bg-surface2 border-l-2 border-l-accent pl-3.5" : "hover:bg-surface2"
                  }`}
                >
                  <div className="font-mono text-[12px] text-fg font-medium">{s.session_id}</div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[10px] font-semibold tracking-wider ${
                        color === "ok"
                          ? "bg-ok/15 text-ok"
                          : color === "err"
                          ? "bg-err/15 text-err"
                          : color === "warn"
                          ? "bg-warn/15 text-warn"
                          : "bg-info/15 text-info"
                      }`}
                    >
                      {s.step_count} 步
                    </span>
                    <span className="font-mono text-[11px] text-dim">{relativeTime(s.started_at)}</span>
                  </div>
                </button>
              );
            })
          )}
        </div>

        <div className="overflow-auto">
          {activeSession ? (
            <SessionDetail session={activeSession} />
          ) : (
            <div className="p-8 text-dim text-[13px]">选择左侧 session 查看详情</div>
          )}
        </div>
      </div>
    </div>
  );
}

function SessionDetail({ session }: { session: SessionSummary }) {
  const [detail, setDetail] = useState<SessionDetailData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);

    api.getSessionDetail(session.session_id)
      .then((data) => {
        if (!cancelled) setDetail(data as SessionDetailData);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [session.session_id]);

  const steps = detail?.steps ?? [];
  const visionModel = "未记录";
  const solverModel = "未记录";

  return (
    <div>
      <div className="flex items-center gap-4 p-4 px-5 border-b border-line">
        <div className="flex-1">
          <div className="font-mono text-[14px] font-medium">{session.session_id}</div>
          <div className="font-mono text-[11px] text-dim mt-0.5">
            视觉模型：{visionModel} · 求解模型：{solverModel} · {session.step_count} 步
          </div>
        </div>
        <div className="flex gap-1.5">
          <button className="h-7 px-2.5 rounded border border-line bg-bg text-fg text-[12px] hover:bg-surface2 active:-translate-y-px">打开目录</button>
          <button className="h-7 px-2.5 rounded border border-line bg-bg text-fg text-[12px] hover:bg-surface2 active:-translate-y-px">加载配置</button>
        </div>
      </div>

      {loading && <div className="p-5 text-dim text-[13px]">加载步骤详情中</div>}
      {error && <div className="p-5 text-err text-[13px]">加载失败：{error}</div>}
      {!loading && !error && steps.length === 0 && (
        <div className="p-5 text-dim text-[13px]">暂无步骤详情</div>
      )}
      {!loading && !error && steps.length > 0 && (
        <div className="p-4 space-y-2">
          {steps.map((step, index) => {
            const confidence = stepConfidence(step);
            return (
              <div key={`${step.step ?? index}-${step.timestamp ?? ""}`} className="grid grid-cols-[56px_88px_72px_1fr_80px_72px] gap-3 items-center p-3 bg-surface1 border border-line rounded">
                <div className="font-mono text-[12px] text-accent">#{step.step ?? index + 1}</div>
                <div className="font-mono text-[12px] text-fg">{stepAnswer(step)}</div>
                <div className="text-[12px] text-muted">{questionTypeLabel(step.question_type)}</div>
                <div className="text-[12px] text-fg truncate">{excerpt(step.question)}</div>
                <div className="font-mono text-[12px] text-info text-right">
                  {confidence === null ? "-" : confidence.toFixed(2)}
                </div>
                <div className="font-mono text-[11px] text-dim text-right">
                  {step.timestamp ? relativeTime(step.timestamp) : "-"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
