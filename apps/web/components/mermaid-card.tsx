"use client";

import { useEffect, useId, useState } from "react";

import { Card } from "@stream2graph/ui";

let mermaidReady: Promise<typeof import("mermaid")> | null = null;
let mermaidInitialized = false;

async function getMermaid() {
  if (!mermaidReady) {
    mermaidReady = import("mermaid");
  }
  const mermaidPackage = await mermaidReady;
  if (!mermaidInitialized) {
    mermaidPackage.default.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: "neutral",
    });
    mermaidInitialized = true;
  }
  return mermaidPackage.default;
}

export function MermaidCard({
  title,
  code,
  height = 360,
}: {
  title: string;
  code: string;
  height?: number;
}) {
  const id = useId().replace(/:/g, "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function render() {
      if (!code.trim()) {
        setSvg("");
        setError("暂无 Mermaid 内容");
        return;
      }
      try {
        const mermaid = await getMermaid();
        const { svg: rendered } = await mermaid.render(`mermaid-${id}`, code);
        if (!active) return;
        setSvg(rendered);
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "渲染失败");
      }
    }
    render();
    return () => {
      active = false;
    };
  }, [code, id]);

  return (
    <Card className="overflow-hidden p-0">
      <div className="border-b border-white/70 px-6 py-5">
        <div className="text-sm font-semibold text-slate-900">{title}</div>
      </div>
      <div className="bg-[linear-gradient(180deg,rgba(255,255,255,0.92),rgba(246,249,255,0.84))] p-5">
        {error ? (
          <div className="rounded-[24px] border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            Mermaid 渲染错误：{error}
          </div>
        ) : (
          <div
            className="overflow-auto rounded-[26px] border border-white/75 bg-white/[0.84] p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]"
            style={{ minHeight: height }}
            dangerouslySetInnerHTML={{ __html: svg }}
          />
        )}
      </div>
    </Card>
  );
}
