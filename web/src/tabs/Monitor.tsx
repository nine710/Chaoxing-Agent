import { useAppStore } from "../lib/store";

export function Monitor() {
  const { screenshot, currentStep, stepHistory } = useAppStore();

  return (
    <div className="grid grid-cols-[1fr_340px] h-full">
      {/* 左：实时画面 + 暂停条 + 决策按钮 */}
      <div className="flex flex-col p-6 gap-3 border-r border-line overflow-auto">
        <div className="flex items-center text-[13px] font-medium">
          实时画面
          <span className="font-mono text-[12px] text-muted ml-1.5">step {currentStep?.step ?? 0}</span>
          <span className="ml-auto font-mono text-[12px] text-muted">
            <span className="text-accent mr-1.5">画面流</span>
            2.0 fps
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center bg-surface1 border border-line rounded-lg overflow-hidden p-6">
          {screenshot ? (
            <img
              src={`data:image/jpeg;base64,${screenshot.image_b64}`}
              alt="实时画面"
              className="max-h-full max-w-full"
              style={{ aspectRatio: `${screenshot.width} / ${screenshot.height}` }}
            />
          ) : (
            <span className="text-dim">未连接 / 等待画面</span>
          )}
        </div>
      </div>

      {/* 右：分块（用 1px 分割线，不用卡片） */}
      <div className="flex flex-col bg-surface1 overflow-auto">
        <div className="p-4 border-b border-line">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[11px] font-semibold tracking-wider uppercase text-dim">当前步</div>
            <div className="font-mono text-[11px] text-dim">{currentStep?.step ?? 0} / 200</div>
          </div>
          <div className="grid grid-cols-[1fr_auto] gap-2 py-1 text-[12px] first:pt-0">
            <span className="text-muted">page state</span>
            <span className="font-mono text-fg">{currentStep?.question ? "题目" : "未开始"}</span>
          </div>
          <div className="grid grid-cols-[1fr_auto] gap-2 py-1 text-[12px]">
            <span className="text-muted">题目数</span>
            <span className="font-mono text-fg">{currentStep?.options?.length ?? 0}</span>
          </div>
        </div>

        <div className="p-4 border-b border-line">
          <div className="flex items-center justify-between mb-3">
            <div className="text-[11px] font-semibold tracking-wider uppercase text-dim">置信度</div>
          </div>
          <div className="grid grid-cols-[1fr_auto_auto] gap-2 items-center py-1 text-[12px]">
            <span className="text-muted">solver</span>
            <div className="w-10 h-[3px] relative rounded-sm border-t border-line-faint">
              <span
                className="absolute top-[-2px] h-[5px] w-px -translate-x-1/2 bg-accent"
                style={{ left: `${Math.min(1, Math.max(0, currentStep?.confidence ?? 0)) * 100}%` }}
              />
            </div>
            <span className="font-mono text-accent min-w-[32px] text-right">
              {(currentStep?.confidence ?? 0).toFixed(2)}
            </span>
          </div>
        </div>

        <div className="p-4 border-b border-line">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-dim mb-3">答案</div>
          <div className="grid grid-cols-[1fr_auto] gap-2 py-1 text-[12px]">
            <span className="text-muted">选项</span>
            <span className="font-mono text-fg">
              {currentStep?.answer?.join(" ") || "未选择"}
            </span>
          </div>
        </div>

        <div className="p-4 flex-1 overflow-auto">
          <div className="text-[11px] font-semibold tracking-wider uppercase text-dim mb-3">最近 5 步</div>
          <div>
            {stepHistory.slice(0, 5).map((s) => (
              <div
                key={s.step}
                className="grid grid-cols-[auto_1fr_auto] gap-2 py-[6px] text-[12px] items-center border-t border-line-faint first:border-t-0"
              >
                <span className="font-mono text-dim text-[11px]">#{s.step}</span>
                <span className="font-mono font-semibold text-fg">{s.answer.join(" ") || "未选择"}</span>
                <span className="font-mono text-[11px] text-dim">
                  {s.confidence.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}