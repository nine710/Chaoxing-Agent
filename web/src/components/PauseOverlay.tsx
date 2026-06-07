import { useAppStore } from "../lib/store";
import { api } from "../lib/tauri-bridge";

export function PauseOverlay() {
  const { pause, clearPause } = useAppStore();
  if (!pause.pending) return null;

  async function decide(d: "retry" | "skip" | "quit") {
    try {
      await api.pauseDecision(d);
    } catch (e) {
      console.error("pauseDecision failed", e);
    } finally {
      clearPause();
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-bg/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-surface1 border border-line rounded-lg p-6 max-w-md w-full">
        <div className="inline-flex items-center gap-1.5 px-2 py-0.5 mb-3 bg-accent-dim text-accent font-mono text-[10px] font-semibold tracking-wider rounded-sm">
          PAUSED
        </div>
        <div className="text-[13px] text-fg mb-1">已暂停</div>
        <div className="font-mono text-[11px] text-dim mb-4">
          {pause.reason ?? "未知原因"}
          {pause.step !== null && <span className="ml-2">（第 {pause.step} 步）</span>}
        </div>
        {pause.screenshot_b64 && (
          <img
            src={`data:image/jpeg;base64,${pause.screenshot_b64}`}
            alt="暂停画面"
            className="w-full rounded border border-line mb-4"
          />
        )}
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => decide("retry")}
            className="inline-flex items-center h-8 px-3 rounded-md border border-accent bg-accent text-accent-fg text-[12px] font-medium hover:bg-[#FBBF24]"
          >
            重试（R）
          </button>
          <button
            onClick={() => decide("skip")}
            className="inline-flex items-center h-8 px-3 rounded-md border border-line bg-bg text-fg text-[12px] font-medium hover:bg-surface2"
          >
            跳过（S）
          </button>
          <button
            onClick={() => decide("quit")}
            className="inline-flex items-center h-8 px-3 rounded-md border border-err/40 text-err text-[12px] font-medium hover:bg-err/10"
          >
            退出（Q）
          </button>
        </div>
      </div>
    </div>
  );
}