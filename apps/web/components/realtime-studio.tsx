"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic, MicOff, Play, RefreshCcw, Save, Send, StopCircle, WandSparkles } from "lucide-react";
import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

import { Badge, Button, Card, Input, SectionHeading, StatCard, Textarea } from "@stream2graph/ui";

import { api } from "@/lib/api";
import { GraphStage } from "@/components/graph-stage";

const LOCAL_SESSION_KEY = "s2g:last-realtime-session";

type TranscriptRow = {
  text: string;
  speaker: string;
  expected_intent?: string | null;
};

function getSpeechRecognitionErrorMessage(errorCode?: string) {
  switch (errorCode) {
    case "network":
      return "浏览器语音识别服务当前不可用。通常是网络、浏览器服务连接或地区环境导致。你可以先改用 Transcript 输入。";
    case "not-allowed":
    case "service-not-allowed":
      return "麦克风权限未开启，或浏览器禁止了语音识别服务。请检查站点权限后重试。";
    case "audio-capture":
      return "没有检测到可用麦克风设备。请确认系统输入设备和浏览器权限。";
    case "no-speech":
      return "没有检测到有效语音输入。请靠近麦克风后重试。";
    case "aborted":
      return "语音识别已中断。";
    case "language-not-supported":
      return "当前浏览器不支持所选语音识别语言。";
    default:
      return "语音识别失败。你可以先改用 Transcript 输入。";
  }
}

function parseTranscriptInput(raw: string): TranscriptRow[] {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split("|").map((part) => part.trim());
      if (parts.length === 1) return { speaker: "user", text: parts[0] };
      if (parts.length === 2) return { speaker: parts[0] || "user", text: parts[1] };
      return { speaker: parts[0] || "user", text: parts[1], expected_intent: parts[2] || null };
    });
}

export function RealtimeStudio() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("研究演示会话");
  const [datasetVersion, setDatasetVersion] = useState("");
  const [transcriptText, setTranscriptText] = useState(
    [
      "expert|First define ingestion flow and source node.|sequential",
      "expert|Then route events to parser and validation service.|sequential",
      "expert|The gateway module connects auth service and data service.|structural",
    ].join("\n"),
  );
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.listDatasets });
  const sessions = useQuery({ queryKey: ["realtime-sessions"], queryFn: api.listRealtimeSessions });

  useEffect(() => {
    if (!datasetVersion && datasets.data?.length) {
      setDatasetVersion(datasets.data.find((item) => item.is_default)?.slug || datasets.data[0].slug);
    }
  }, [datasetVersion, datasets.data]);

  useEffect(() => {
    const stored = window.localStorage.getItem(LOCAL_SESSION_KEY);
    if (stored) setCurrentSessionId(stored);
  }, []);

  const createSession = useMutation({
    mutationFn: () =>
      api.createRealtimeSession({
        title,
        dataset_version_slug: datasetVersion || null,
        min_wait_k: 1,
        base_wait_k: 2,
        max_wait_k: 4,
      }),
    onSuccess: (data) => {
      setCurrentSessionId(data.session_id);
      window.localStorage.setItem(LOCAL_SESSION_KEY, data.session_id);
      queryClient.invalidateQueries({ queryKey: ["realtime-sessions"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  const snapshotMutation = useMutation({
    mutationFn: (sessionId: string) => api.snapshotRealtime(sessionId),
    onSuccess: (data) => {
      setSnapshot(data);
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["realtime-sessions"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  useEffect(() => {
    if (currentSessionId) {
      snapshotMutation.mutate(currentSessionId);
    }
    // `useMutation()` returns a new object identity per render; only auto-snapshot when session changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSessionId]);

  async function ensureSession() {
    if (currentSessionId) return currentSessionId;
    const created = await createSession.mutateAsync();
    return created.session_id;
  }

  const sendTranscript = useMutation({
    mutationFn: async () => {
      const sessionId = await ensureSession();
      const rows = parseTranscriptInput(transcriptText);
      let last = null;
      for (let i = 0; i < rows.length; i += 1) {
        last = await api.addRealtimeChunk(sessionId, {
          timestamp_ms: i * 450,
          text: rows[i].text,
          speaker: rows[i].speaker,
          expected_intent: rows[i].expected_intent || null,
        });
      }
      return last;
    },
    onSuccess: (data) => {
      if (data) setSnapshot({ session_id: data.session_id, pipeline: data.pipeline, evaluation: data.evaluation });
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["realtime-sessions"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  const flushMutation = useMutation({
    mutationFn: (sessionId: string) => api.flushRealtime(sessionId),
    onSuccess: (data) => setSnapshot(data),
    onError: (err) => setError((err as Error).message),
  });

  const closeMutation = useMutation({
    mutationFn: (sessionId: string) => api.closeRealtime(sessionId),
    onSuccess: () => {
      if (currentSessionId) window.localStorage.removeItem(LOCAL_SESSION_KEY);
      setCurrentSessionId(null);
      setSnapshot(null);
      queryClient.invalidateQueries({ queryKey: ["realtime-sessions"] });
    },
    onError: (err) => setError((err as Error).message),
  });

  const saveReportMutation = useMutation({
    mutationFn: (sessionId: string) => api.saveRealtimeReport(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports"] }),
    onError: (err) => setError((err as Error).message),
  });

  const rendererState = snapshot?.pipeline?.renderer_state || {};
  const events = snapshot?.pipeline?.events || [];

  const startRecognition = async () => {
    const sessionId = await ensureSession();
    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setError("当前浏览器不支持 Web Speech API");
      return;
    }
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "zh-CN";
    recognition.continuous = true;
    recognition.interimResults = false;
    setError(null);
    recognition.onresult = async (event: any) => {
      const lastResult = event.results[event.results.length - 1];
      const text = lastResult[0].transcript;
      const data = await api.addRealtimeChunk(sessionId, { text, speaker: "speaker", is_final: true });
      setSnapshot({ session_id: data.session_id, pipeline: data.pipeline, evaluation: data.evaluation });
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setListening(false);
    };
    recognition.onerror = (evt: any) => {
      recognitionRef.current = null;
      setListening(false);
      setError(getSpeechRecognitionErrorMessage(evt?.error));
    };
    try {
      recognition.start();
    } catch (err) {
      recognitionRef.current = null;
      setListening(false);
      setError(err instanceof Error ? err.message : "语音识别启动失败");
      return;
    }
    recognitionRef.current = recognition;
    setListening(true);
  };

  const summaryCards = useMemo(() => {
    const metrics = snapshot?.evaluation?.metrics ?? {};
    return [
      { label: "E2E P95", value: metrics.e2e_latency_p95_ms ?? "-" },
      { label: "Intent Acc", value: metrics.intent_accuracy ?? "-" },
      { label: "Flicker", value: metrics.flicker_mean ?? "-" },
      { label: "Mental Map", value: metrics.mental_map_mean ?? "-" },
    ];
  }, [snapshot?.evaluation?.metrics]);

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Realtime Studio"
        title="实时成图工作台"
        description="用正式平台方式管理会话、事件流、增量图和实时评测结果。刷新页面后会优先恢复最近一次活动会话。"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{currentSessionId ? `Session ${currentSessionId}` : "未创建会话"}</Badge>
            {snapshot?.evaluation?.realtime_eval_pass === true ? (
              <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700">评测通过</Badge>
            ) : null}
          </div>
        }
      />

      {error ? (
        <div className="rounded-[24px] border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      <Card className="soft-enter space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-base font-semibold text-slate-950">推荐流程</div>
            <p className="mt-2 text-sm leading-6 text-slate-600">先创建会话，再发送 transcript 或打开麦克风，最后在右侧查看增量图和评测结果。</p>
          </div>
          <Badge>{listening ? "麦克风采集中" : "可使用 transcript 或麦克风"}</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            ["1", "创建会话", "设置标题和数据集，创建当前演示会话。"],
            ["2", "输入内容", "粘贴 transcript，或直接打开麦克风采集。"],
            ["3", "查看结果", "在图舞台、事件流和评测页签之间切换查看。"],
          ].map(([step, titleText, desc]) => (
            <div key={step} className="rounded-[22px] border border-white/70 bg-white/[0.56] px-4 py-4">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--accent-strong)]">Step {step}</div>
              <div className="mt-2 text-sm font-semibold text-slate-900">{titleText}</div>
              <div className="mt-2 text-sm leading-6 text-slate-600">{desc}</div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[390px_minmax(0,1fr)]">
        <Card className="soft-enter space-y-6">
          <div className="space-y-3">
            <label className="text-sm font-medium text-slate-700">会话标题</label>
            <Input value={title} onChange={(event: ChangeEvent<HTMLInputElement>) => setTitle(event.target.value)} />
          </div>
          <div className="space-y-3">
            <label className="text-sm font-medium text-slate-700">数据集版本</label>
            <select
              className="h-12 w-full rounded-[22px] border border-white/70 bg-white/[0.72] px-4 text-sm outline-none transition focus:border-[var(--accent)] focus:bg-white focus:ring-4 focus:ring-[rgba(77,124,255,0.12)]"
              value={datasetVersion}
              onChange={(event: ChangeEvent<HTMLSelectElement>) => setDatasetVersion(event.target.value)}
            >
              {datasets.data?.map((item) => (
                <option key={item.slug} value={item.slug}>
                  {item.slug}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-sm font-medium text-slate-700">Transcript 输入</label>
              <p className="mt-2 text-xs leading-6 text-slate-500">支持 `speaker | text | expected_intent`，一行一条，适合演示和快速回放。</p>
            </div>
            <Textarea
              rows={15}
              value={transcriptText}
              onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setTranscriptText(event.target.value)}
            />
          </div>
          <div className="grid gap-3">
            <Button className="py-3" onClick={() => createSession.mutate()} disabled={createSession.isPending}>
              <WandSparkles className="h-4 w-4" />
              {currentSessionId ? "重新创建会话" : "创建会话"}
            </Button>
            <Button className="py-3" variant="secondary" onClick={() => sendTranscript.mutate()} disabled={sendTranscript.isPending}>
              <Send className="h-4 w-4" />
              发送当前 Transcript
            </Button>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="secondary"
                className="py-3"
                onClick={() => (currentSessionId ? snapshotMutation.mutate(currentSessionId) : null)}
                disabled={!currentSessionId}
              >
                <RefreshCcw className="h-4 w-4" />
                快照
              </Button>
              <Button
                variant="secondary"
                className="py-3"
                onClick={() => (currentSessionId ? flushMutation.mutate(currentSessionId) : null)}
                disabled={!currentSessionId}
              >
                <Play className="h-4 w-4" />
                Flush
              </Button>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button className="py-3" variant="ghost" onClick={() => void startRecognition()} disabled={listening}>
                <Mic className="h-4 w-4" />
                麦克风开始
              </Button>
              <Button
                variant="ghost"
                className="py-3"
                onClick={() => {
                  recognitionRef.current?.stop?.();
                  setListening(false);
                }}
                disabled={!listening}
              >
                <MicOff className="h-4 w-4" />
                麦克风停止
              </Button>
            </div>
            <div className="rounded-[20px] border border-white/70 bg-white/[0.52] px-4 py-3 text-xs leading-6 text-slate-500">
              麦克风功能依赖浏览器的 Web Speech 服务。如果提示网络或服务不可用，通常不是项目后端报错，先用
              Transcript 输入会更稳定。
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="secondary"
                className="py-3"
                onClick={() => (currentSessionId ? saveReportMutation.mutate(currentSessionId) : null)}
                disabled={!currentSessionId}
              >
                <Save className="h-4 w-4" />
                保存报告
              </Button>
              <Button
                variant="danger"
                className="py-3"
                onClick={() => (currentSessionId ? closeMutation.mutate(currentSessionId) : null)}
                disabled={!currentSessionId}
              >
                <StopCircle className="h-4 w-4" />
                关闭会话
              </Button>
            </div>
          </div>

          <div className="space-y-3 border-t border-white/[0.65] pt-2">
            <div className="text-sm font-medium text-slate-700">最近会话</div>
            <div className="max-h-[320px] space-y-2 overflow-auto pr-1">
              {sessions.data?.map((item) => (
                <button
                  key={item.session_id}
                  className={`lift-hover w-full rounded-[22px] border px-4 py-3.5 text-left text-sm ${
                    currentSessionId === item.session_id
                      ? "border-[var(--accent)] bg-[rgba(77,124,255,0.08)]"
                      : "border-white/70 bg-white/[0.64]"
                  }`}
                  onClick={() => {
                    setCurrentSessionId(item.session_id);
                    window.localStorage.setItem(LOCAL_SESSION_KEY, item.session_id);
                  }}
                >
                  <div className="font-semibold text-slate-900">{item.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.session_id}</div>
                </button>
              ))}
            </div>
          </div>
        </Card>

        <div className="soft-enter soft-enter-delay-1 space-y-6">
          <GraphStage title="增量图舞台" nodes={rendererState.nodes || []} edges={rendererState.edges || []} />
          <Tabs.Root defaultValue="events" className="space-y-5">
            <Tabs.List className="glass-panel inline-flex flex-wrap gap-2 rounded-full border border-white/70 p-1.5">
              {[
                ["events", "事件流"],
                ["metrics", "评测指标"],
                ["pipeline", "运行摘要"],
              ].map(([value, label]) => (
                <Tabs.Trigger
                  key={value}
                  value={value}
                  className="rounded-full border border-transparent bg-transparent px-4 py-2.5 text-sm font-medium text-slate-600 transition data-[state=active]:border-white/80 data-[state=active]:bg-white/[0.88] data-[state=active]:text-slate-950"
                >
                  {label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>

            <Tabs.Content value="events">
              <Card>
                <div className="mb-5 flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">事件流</div>
                    <p className="mt-1 text-xs leading-6 text-slate-500">这里只保留最近更新，帮助你快速判断图是否按预期演进。</p>
                  </div>
                  <Badge>{events.length} updates</Badge>
                </div>
                <div className="max-h-[460px] space-y-3 overflow-auto pr-2">
                  {events.length ? (
                    events.slice(-12).map((event: Record<string, any>, index: number) => (
                      <div
                        key={`${event.update?.update_id}-${index}`}
                        className="glass-panel rounded-[24px] border border-white/70 p-4"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-sm font-semibold text-slate-900">
                            Update #{event.update?.update_id} · {event.update?.intent_type}
                          </div>
                          <Badge>{event.e2e_latency_ms} ms</Badge>
                        </div>
                        <div className="mt-2 text-xs leading-6 text-slate-600">{event.update?.transcript_text}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-[22px] border border-dashed border-slate-300 p-5 text-sm text-slate-500">
                      还没有增量事件。创建会话后发送 transcript 或启动麦克风。
                    </div>
                  )}
                </div>
              </Card>
            </Tabs.Content>

            <Tabs.Content value="metrics">
              <div className="space-y-6">
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  {summaryCards.map((item) => (
                    <StatCard key={item.label} label={item.label} value={String(item.value)} />
                  ))}
                </div>
                <Card>
                  <div className="mb-4 text-sm font-semibold text-slate-900">实时评测</div>
                  <pre className="rounded-[24px] bg-slate-950 p-5 text-xs leading-6 text-slate-100">
                    {JSON.stringify(snapshot?.evaluation || {}, null, 2)}
                  </pre>
                </Card>
              </div>
            </Tabs.Content>

            <Tabs.Content value="pipeline">
              <Card>
                <div className="mb-4 text-sm font-semibold text-slate-900">Pipeline 摘要</div>
                <pre className="rounded-[24px] bg-slate-950 p-5 text-xs leading-6 text-slate-100">
                  {JSON.stringify(snapshot?.pipeline?.summary || {}, null, 2)}
                </pre>
              </Card>
            </Tabs.Content>
          </Tabs.Root>
        </div>
      </div>
    </div>
  );
}
