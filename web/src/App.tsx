import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

export default function App() {
  const [greeting, setGreeting] = useState("");

  useEffect(() => {
    invoke<string>("greet", { name: "测试" }).then(setGreeting).catch(() => setGreeting(""));
  }, []);

  return (
    <div className="flex h-full items-center justify-center text-2xl">
      {greeting || "加载中..."}
    </div>
  );
}