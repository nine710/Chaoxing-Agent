import { useEffect, useRef, useState } from "react";
import { useAppStore } from "../lib/store";

export function Logs() {
  const { logs, clearLogs } = useAppStore();
  const [filter, setFilter] = useState("");
  const [levels, setLevels] = useState<Record<string, boolean>>({
    DEBUG: true, INFO: true, WARN: true, ERROR: true,
  });
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filtered = logs.filter((l) => {
    if (!levels[l.level]) return false;
    if (filter && !l.message.toLowerCase().includes(filter.toLowerCase())) return false;
    return true;
  });

  const lvlClass = (lvl: string) => {
    if (lvl === "INFO") return "text-info";
    if (lvl === "WARN") return "text-warn";
    if (lvl === "ERROR") return "text-err";
    return "text-dim";
  };

  const lvlLabel = (lvl: string) => {
    if (lvl === "INFO") return "INF";
    if (lvl === "WARN") return "WRN";
    if (lvl === "ERROR") return "ERR";
    return "DBG";
  };

  return (
    <div className="flex flex-col h-full p-4 max-w-[1200px] mx-auto w-full">
      <div className="text-[22px] font-semibold tracking-tight mb-1">日志</div>
      <div className="text-[13px] text-muted mb-4">实时 stderr 流，来源 Python 子进程</div>

      <div className="flex items-center gap-2 mb-3">
        <div className="flex-1 flex items-center gap-2 h-8 px-[10px] bg-surface1 border border-line rounded">
          <span className="text-dim text-[12px]">搜索</span>
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="搜索日志"
            className="flex-1 bg-transparent font-mono text-[12px] text-fg outline-none"
          />
        </div>
        <div className="flex gap-1">
          {Object.keys(levels).map((lvl) => (
            <button
              key={lvl}
              onClick={() => setLevels({ ...levels, [lvl]: !levels[lvl] })}
              className={`px-2 py-1 rounded font-mono text-[10px] font-semibold tracking-wider border transition-colors ${
                levels[lvl]
                  ? lvl === "INFO" ? "text-info border-info/30"
                    : lvl === "WARN" ? "text-warn border-warn/30"
                    : lvl === "ERROR" ? "text-err border-err/30"
                    : "text-dim border-line"
                  : "text-dim border-line"
              }`}
            >
              {lvl}
            </button>
          ))}
        </div>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`h-8 px-[10px] rounded border border-line text-[12px] ${autoScroll ? "text-fg bg-surface2" : "text-dim"}`}
        >
          自动滚动
        </button>
        <button
          onClick={clearLogs}
          className="h-8 px-[10px] rounded border border-line bg-surface1 text-fg text-[12px] hover:bg-surface2"
        >
          清空
        </button>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-auto bg-log border border-line rounded-lg p-4 font-mono text-[12px] leading-relaxed"
      >
        {filtered.length === 0 ? (
          <div className="text-dim">无日志</div>
        ) : (
          filtered.map((l, i) => (
            <div key={i} className="grid grid-cols-[100px_60px_1fr] gap-3 py-px">
              <span className="text-dim">{l.ts.slice(11, 23)}</span>
              <span className={`font-semibold ${lvlClass(l.level)}`}>{lvlLabel(l.level)}</span>
              <span className="text-fg break-all whitespace-pre-wrap">{l.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}