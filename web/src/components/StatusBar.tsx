import { useAppStore } from "../lib/store";

export function StatusBar() {
  const { totalSteps, isRunning, currentStep, connection, target } = useAppStore();
  const confidence = currentStep?.confidence ?? null;

  return (
    <footer className="flex items-center h-7 px-5 bg-surface1 border-t border-line font-mono text-[11px] text-dim gap-6">
      <span>
        <span className="text-dim mr-1.5">步数</span>
        <span className="text-fg">{totalSteps}</span>
      </span>
      <span>
        <span className="text-dim mr-1.5">状态</span>
        <span className={isRunning ? "text-ok" : "text-fg"}>
          {isRunning ? "运行中" : connection}
        </span>
      </span>
      {confidence !== null && (
        <span>
          <span className="text-dim mr-1.5">置信度</span>
          <span className="text-fg">{confidence.toFixed(2)}</span>
        </span>
      )}
      {target && (
        <span>
          <span className="text-dim mr-1.5">目标</span>
          <span className="text-fg">{target.title || target.processName}</span>
        </span>
      )}
      <div className="flex-1" />
      <span className="text-dim">v0.2.0</span>
    </footer>
  );
}