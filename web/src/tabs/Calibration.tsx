import { useEffect, useState } from "react";
import { useAppStore } from "../lib/store";
import { api, events } from "../lib/tauri-bridge";

export function Calibration() {
  const { isRunning, calibration, setCalibration } = useAppStore();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getCalibration()
      .then(setCalibration)
      .catch((e) => setError(String(e)));
  }, [setCalibration]);

  useEffect(() => {
    const un = events.calibrationChanged(() => {
      api
        .getCalibration()
        .then(setCalibration)
        .catch((e) => setError(String(e)));
    });
    return () => {
      un.then((u) => u());
    };
  }, [setCalibration]);

  async function launch() {
    setBusy(true);
    setError(null);
    try {
      await api.launchCalibrationWizard();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const target = calibration?.target;

  return (
    <div className="grid grid-cols-[1fr_360px] h-full">
      <div className="p-8 border-r border-line overflow-auto">
        <div className="text-[22px] font-semibold tracking-tight mb-1">标定</div>
        <div className="text-[13px] text-muted mb-8">绑定目标窗口 + 框选手机画面区域</div>

        <div className="flex gap-[10px] p-3.5 bg-surface1 border border-line border-l-2 border-l-accent rounded mb-6">
          <span className="text-accent text-[14px]">ⓘ</span>
          <div className="text-[12.5px] text-muted leading-relaxed">
            <span className="text-fg font-medium">框选在原生 Python 向导中完成。</span>
            校准是低频、一次性的设置，强行搬到桌面窗口里会损失 Win32 坐标精度。点击下方按钮启动向导，完成后这里会自动刷新。
          </div>
        </div>

        <Field label="目标窗口" hint={target ? `hwnd ${target.hwnd.toString(16)}` : ""}>
          <input
            className="w-full h-[34px] px-[10px] font-mono text-[12px] bg-surface1 text-fg border border-line rounded focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-dim read-only:text-muted"
            value={target?.title ?? ""}
            readOnly
            placeholder="未绑定"
          />
        </Field>

        <Field label="客户区" hint="px (x1 y1 x2 y2)">
          <input
            className="w-full h-[34px] px-[10px] font-mono text-[12px] bg-surface1 text-fg border border-line rounded focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-dim read-only:text-muted"
            value={calibration?.client_rect?.join(" ") ?? ""}
            readOnly
            placeholder="未标定"
          />
        </Field>

        <Field label="手机视口" hint="px (x y w h)">
          <input
            className="w-full h-[34px] px-[10px] font-mono text-[12px] bg-surface1 text-fg border border-line rounded focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-dim read-only:text-muted"
            value={
              calibration?.phone_viewport_in_client
                ? `${calibration.phone_viewport_in_client.x} ${calibration.phone_viewport_in_client.y} ${calibration.phone_viewport_in_client.width} ${calibration.phone_viewport_in_client.height}`
                : ""
            }
            readOnly
            placeholder="未标定"
          />
        </Field>

        <Field label="视口比例" hint="fraction">
          <input
            className="w-full h-[34px] px-[10px] font-mono text-[12px] bg-surface1 text-fg border border-line rounded focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-dim read-only:text-muted"
            value={
              calibration?.phone_viewport_ratio
                ? `${calibration.phone_viewport_ratio.x} ${calibration.phone_viewport_ratio.y} ${calibration.phone_viewport_ratio.width} ${calibration.phone_viewport_ratio.height}`
                : ""
            }
            readOnly
            placeholder="未标定"
          />
        </Field>

        <div className="mt-3 p-4 bg-surface1 border border-dashed border-line rounded flex items-center gap-3">
          <div className="flex-1 text-[12px] text-muted">
            <span className="text-fg font-medium">运行标定向导</span>
            <br />
            唤起原生窗口，截图 + 拖拽 + 实时坐标回显
          </div>
          <button
            onClick={launch}
            disabled={busy || isRunning}
            className="inline-flex items-center h-8 px-3.5 rounded-md border border-accent bg-accent text-accent-fg text-[12.5px] font-medium transition-all duration-150 hover:bg-[#FBBF24] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy ? "启动中" : isRunning ? "运行中不可改" : "启动向导"}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-err/10 border border-err/40 rounded text-[12px] text-err font-mono">
            {error}
          </div>
        )}
      </div>

      <div className="bg-surface1 p-8">
        <SidebarBlock label="窗口绑定">
          <div className="font-mono text-[12px] text-ok mb-2">已绑定</div>
          <KV k="process" v={target?.process_name ?? "—"} />
          <KV k="pid" v={target?.pid?.toString() ?? "—"} />
          <KV k="title" v={target?.title ?? "—"} />
        </SidebarBlock>
        <SidebarBlock label="视口">
          <div className="font-mono text-[12px] text-warn mb-2">已锁定</div>
          <KV k="x, y" v={
            calibration?.phone_viewport_in_client
              ? `${calibration.phone_viewport_in_client.x}, ${calibration.phone_viewport_in_client.y}`
              : "—"
          } />
          <KV k="w x h" v={
            calibration?.phone_viewport_in_client
              ? `${calibration.phone_viewport_in_client.width} x ${calibration.phone_viewport_in_client.height}`
              : "—"
          } />
          <KV k="ratio" v={
            calibration?.phone_viewport_ratio
              ? `${calibration.phone_viewport_ratio.width} x ${calibration.phone_viewport_ratio.height}`
              : "—"
          } />
        </SidebarBlock>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="mb-[18px]">
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="text-[12px] font-medium text-fg">{label}</span>
        {hint && <span className="font-mono text-[11px] text-dim">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function SidebarBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-7 pb-5 border-b border-line last:border-b-0">
      <div className="text-[10.5px] font-semibold uppercase tracking-wider text-dim mb-[10px]">{label}</div>
      {children}
    </div>
  );
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between py-[2px] font-mono text-[11.5px]">
      <span className="text-dim">{k}</span>
      <span className="text-fg">{v}</span>
    </div>
  );
}