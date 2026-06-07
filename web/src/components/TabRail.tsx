import { useAppStore, type ActiveTab } from "../lib/store";

const tabs: { key: ActiveTab; label: string }[] = [
  { key: "实时监控", label: "实时监控" },
  { key: "标定", label: "标定" },
  { key: "配置", label: "配置" },
  { key: "历史", label: "历史" },
  { key: "日志", label: "日志" },
];

export function TabRail() {
  const { activeTab, setActiveTab } = useAppStore();
  return (
    <nav className="flex items-stretch h-10 px-5 border-b border-line bg-bg">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => setActiveTab(t.key)}
          className={`relative h-10 px-4 text-[13px] font-medium transition-colors duration-150 ${
            activeTab === t.key
              ? "text-fg"
              : "text-dim hover:text-muted"
          }`}
        >
          {t.label}
          {activeTab === t.key && (
            <span className="absolute left-0 right-0 -bottom-px h-px bg-accent" />
          )}
        </button>
      ))}
    </nav>
  );
}