const state = {
  pipelineResult: null,
  evaluationResult: null,
  unifiedResult: null,
  playbackTimer: null,
  playbackIndex: 0,
  graph: {
    nodes: new Map(),
    edges: new Set(),
  },
  live: {
    sessionId: null,
    recognition: null,
    micActive: false,
    startWallMs: 0,
    sendQueue: Promise.resolve(),
  },
};

const refs = {
  transcriptInput: document.getElementById("transcript-input"),
  datasetDir: document.getElementById("dataset-dir"),
  maxFiles: document.getElementById("max-files"),
  realtimeMode: document.getElementById("realtime-mode"),
  timeScale: document.getElementById("time-scale"),
  baseWaitK: document.getElementById("base-wait-k"),
  maxWaitK: document.getElementById("max-wait-k"),
  speechLang: document.getElementById("speech-lang"),
  liveStatus: document.getElementById("live-session-status"),
  liveTranscriptLog: document.getElementById("live-transcript-log"),
  timeline: document.getElementById("timeline"),
  evalSummary: document.getElementById("eval-summary"),
  unifiedSummary: document.getElementById("unified-summary"),
  toast: document.getElementById("toast"),
  svg: document.getElementById("graph-svg"),
  mE2EP95: document.getElementById("m-e2e-p95"),
  mIntentAcc: document.getElementById("m-intent-acc"),
  mFlicker: document.getElementById("m-flicker"),
  mMental: document.getElementById("m-mental"),
};

const sampleTranscript = [
  "expert|First define ingestion flow and source node.|sequential",
  "expert|Then route events to parser and validation service.|sequential",
  "expert|The gateway module connects auth service and data service.|structural",
  "expert|Entity user relates to order by one-to-many relation.|relational",
  "expert|Finally compare baseline and optimized latency.|contrastive",
].join("\n");

function showToast(msg) {
  refs.toast.textContent = msg;
  refs.toast.classList.add("show");
  window.clearTimeout(refs.toast._timer);
  refs.toast._timer = window.setTimeout(() => refs.toast.classList.remove("show"), 2200);
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function setSessionStatus(text) {
  refs.liveStatus.textContent = text;
}

function appendLiveLog(line) {
  const prev = refs.liveTranscriptLog.value;
  refs.liveTranscriptLog.value = prev ? `${prev}\n${line}` : line;
  refs.liveTranscriptLog.scrollTop = refs.liveTranscriptLog.scrollHeight;
}

function parseTranscriptLines(text) {
  const lines = text
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
  const chunks = [];
  lines.forEach((line, idx) => {
    const parts = line.split("|").map((p) => p.trim());
    let speaker = "user";
    let msg = "";
    let expectedIntent = null;
    if (parts.length === 1) {
      msg = parts[0];
    } else if (parts.length === 2) {
      speaker = parts[0] || "user";
      msg = parts[1];
    } else {
      speaker = parts[0] || "user";
      msg = parts[1];
      expectedIntent = parts[2] || null;
    }
    if (!msg) return;
    chunks.push({
      timestamp_ms: idx * 450,
      text: msg,
      speaker,
      expected_intent: expectedIntent,
      is_final: true,
    });
  });
  return chunks;
}

async function apiPost(path, payload) {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await resp.json();
  if (!resp.ok || !data.ok) {
    throw new Error(data.error || `HTTP ${resp.status}`);
  }
  return data;
}

function initSVG() {
  refs.svg.innerHTML = `
    <defs>
      <marker id="arrowHead" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
        <path d="M0,0 L8,4 L0,8 Z" fill="rgba(21,90,154,0.64)"></path>
      </marker>
    </defs>
    <g id="edges-layer"></g>
    <g id="nodes-layer"></g>
  `;
}

function clearGraph() {
  state.graph.nodes.clear();
  state.graph.edges.clear();
  state.playbackIndex = 0;
  initSVG();
}

function ensureNode(nodeId, label = nodeId) {
  if (!state.graph.nodes.has(nodeId)) {
    const idx = state.graph.nodes.size;
    const baseX = 170 + (idx % 7) * 150;
    const baseY = 120 + Math.floor(idx / 7) * 120;
    state.graph.nodes.set(nodeId, {
      id: nodeId,
      label,
      x: baseX,
      y: baseY,
      tx: baseX,
      ty: baseY,
    });
  } else if (label && label !== nodeId) {
    state.graph.nodes.get(nodeId).label = label;
  }
}

function applyOperations(operations) {
  operations.forEach((op) => {
    if (op.op === "add_node") {
      ensureNode(op.id, op.label || op.id);
    }
    if (op.op === "add_edge") {
      ensureNode(op.from, op.from);
      ensureNode(op.to, op.to);
      state.graph.edges.add(`${op.from}__${op.to}`);
    }
  });
  relaxLayout();
}

function relaxLayout(iter = 34) {
  const nodes = Array.from(state.graph.nodes.values());
  if (nodes.length === 0) return;
  for (let k = 0; k < iter; k += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      let fx = 0;
      let fy = 0;
      for (let j = 0; j < nodes.length; j += 1) {
        if (i === j) continue;
        const a = nodes[i];
        const b = nodes[j];
        const dx = a.tx - b.tx;
        const dy = a.ty - b.ty;
        const dist = Math.hypot(dx, dy) + 0.001;
        if (dist < 110) {
          const push = (110 - dist) / 110;
          fx += (dx / dist) * push * 11;
          fy += (dy / dist) * push * 11;
        }
      }
      nodes[i].tx = Math.max(70, Math.min(1130, nodes[i].tx + fx * 0.08));
      nodes[i].ty = Math.max(70, Math.min(620, nodes[i].ty + fy * 0.08));
    }
  }
}

function renderGraphFrame() {
  const edgeLayer = refs.svg.querySelector("#edges-layer");
  const nodeLayer = refs.svg.querySelector("#nodes-layer");
  edgeLayer.innerHTML = "";
  nodeLayer.innerHTML = "";

  for (const edgeKey of state.graph.edges) {
    const [srcId, dstId] = edgeKey.split("__");
    const src = state.graph.nodes.get(srcId);
    const dst = state.graph.nodes.get(dstId);
    if (!src || !dst) continue;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("class", "edge-line");
    line.setAttribute("x1", String(src.x));
    line.setAttribute("y1", String(src.y));
    line.setAttribute("x2", String(dst.x));
    line.setAttribute("y2", String(dst.y));
    line.setAttribute("marker-end", "url(#arrowHead)");
    edgeLayer.appendChild(line);
  }

  for (const node of state.graph.nodes.values()) {
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("transform", `translate(${node.x}, ${node.y})`);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("class", "node-circle");
    circle.setAttribute("r", "28");
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("class", "node-label");
    text.setAttribute("y", "4");
    text.textContent = (node.label || node.id).slice(0, 14);
    g.appendChild(circle);
    g.appendChild(text);
    nodeLayer.appendChild(g);
  }
}

function animateNodes() {
  for (const node of state.graph.nodes.values()) {
    node.x += (node.tx - node.x) * 0.16;
    node.y += (node.ty - node.y) * 0.16;
  }
  renderGraphFrame();
  window.requestAnimationFrame(animateNodes);
}

function ensurePipelineResultContainer() {
  if (!state.pipelineResult) {
    state.pipelineResult = {
      meta: {},
      summary: {},
      events: [],
    };
  }
  if (!state.pipelineResult.events) {
    state.pipelineResult.events = [];
  }
}

function renderTimeline(events, activeIndex = -1) {
  refs.timeline.innerHTML = "";
  events.forEach((ev, idx) => {
    const div = document.createElement("div");
    div.className = `timeline-item ${idx === activeIndex ? "active" : ""}`;
    const update = ev.update || {};
    const frame = ev.render_frame || {};
    div.textContent =
      `#${update.update_id ?? idx + 1} ` +
      `${update.intent_type || "unknown"} | ` +
      `ops:${(update.operations || []).length} | ` +
      `e2e:${ev.e2e_latency_ms ?? "-"}ms | ` +
      `flicker:${frame.flicker_index ?? "-"}`;
    refs.timeline.appendChild(div);
  });
}

function stopPlayback() {
  if (state.playbackTimer) {
    clearInterval(state.playbackTimer);
    state.playbackTimer = null;
  }
}

function startPlayback() {
  const events = state.pipelineResult?.events || [];
  if (!events.length) {
    showToast("没有可播放的事件");
    return;
  }
  stopPlayback();
  state.playbackTimer = window.setInterval(() => {
    if (state.playbackIndex >= events.length) {
      stopPlayback();
      return;
    }
    const ev = events[state.playbackIndex];
    applyOperations(ev.update?.operations || []);
    renderTimeline(events, state.playbackIndex);
    state.playbackIndex += 1;
  }, 520);
}

function resetPlayback() {
  stopPlayback();
  clearGraph();
  renderTimeline(state.pipelineResult?.events || [], -1);
}

function updateMetricCardsFromSummary(summary, evalMetrics = null) {
  refs.mE2EP95.textContent =
    evalMetrics?.e2e_latency_p95_ms != null
      ? `${Number(evalMetrics.e2e_latency_p95_ms).toFixed(1)} ms`
      : `${Number(summary?.latency_e2e_ms?.p95 || 0).toFixed(1)} ms`;
  refs.mIntentAcc.textContent =
    evalMetrics?.intent_accuracy != null
      ? `${(Number(evalMetrics.intent_accuracy) * 100).toFixed(1)}%`
      : summary?.intent_labeled_accuracy != null
        ? `${(Number(summary.intent_labeled_accuracy) * 100).toFixed(1)}%`
        : "-";
  refs.mFlicker.textContent = Number(summary?.renderer_stability?.flicker_index?.mean || 0).toFixed(3);
  refs.mMental.textContent = Number(summary?.renderer_stability?.mental_map_score?.mean || 0).toFixed(3);
}

function updateMetricCards() {
  const summary = state.pipelineResult?.summary || {};
  const ev = state.evaluationResult?.metrics || null;
  updateMetricCardsFromSummary(summary, ev);
}

function appendEventsAndRender(events) {
  ensurePipelineResultContainer();
  events.forEach((ev) => {
    state.pipelineResult.events.push(ev);
    applyOperations(ev.update?.operations || []);
  });
  const active = state.pipelineResult.events.length - 1;
  renderTimeline(state.pipelineResult.events, active);
}

async function runPipelineAndRender() {
  const chunks = parseTranscriptLines(refs.transcriptInput.value);
  if (!chunks.length) {
    showToast("请先输入 transcript");
    return;
  }
  showToast("正在运行闭环...");
  const payload = {
    chunks,
    realtime: refs.realtimeMode.value === "true",
    time_scale: Number(refs.timeScale.value || 1),
    base_wait_k: Number(refs.baseWaitK.value || 2),
    max_wait_k: Number(refs.maxWaitK.value || 4),
  };
  const data = await apiPost("/api/pipeline/run", payload);
  state.pipelineResult = data.result;
  state.evaluationResult = null;
  refs.evalSummary.textContent = pretty({
    mode: state.pipelineResult.meta?.mode,
    updates_emitted: state.pipelineResult.summary?.updates_emitted,
    latency_e2e_ms: state.pipelineResult.summary?.latency_e2e_ms,
    boundary_distribution: state.pipelineResult.summary?.boundary_distribution,
  });
  resetPlayback();
  updateMetricCards();
  showToast("闭环执行完成，开始播放");
  startPlayback();
}

async function runRealtimeEvaluation() {
  const chunks = parseTranscriptLines(refs.transcriptInput.value);
  if (!chunks.length) {
    showToast("请先输入 transcript");
    return;
  }
  showToast("正在运行实时评测...");
  const payload = {
    chunks,
    realtime: refs.realtimeMode.value === "true",
    time_scale: Number(refs.timeScale.value || 1),
    base_wait_k: Number(refs.baseWaitK.value || 2),
    max_wait_k: Number(refs.maxWaitK.value || 4),
    latency_p95_threshold_ms: 2000,
    flicker_mean_threshold: 6.0,
    mental_map_min: 0.85,
    intent_accuracy_threshold: 0.8,
  };
  const data = await apiPost("/api/pipeline/evaluate", payload);
  state.pipelineResult = data.pipeline;
  state.evaluationResult = data.evaluation;
  refs.evalSummary.textContent = pretty(state.evaluationResult);
  resetPlayback();
  updateMetricCards();
  startPlayback();
  showToast(`评测完成: ${state.evaluationResult.realtime_eval_pass ? "PASS" : "未通过"}`);
}

async function runUnifiedEval() {
  if (!state.evaluationResult) {
    showToast("请先运行实时评测，再执行统一评测");
    return;
  }
  showToast("正在运行统一训练前评测...");
  const payload = {
    dataset_dir: refs.datasetDir.value.trim(),
    max_files: Number(refs.maxFiles.value || 0),
    realtime_evaluation: state.evaluationResult,
  };
  const data = await apiPost("/api/pretrain/unified", payload);
  state.unifiedResult = data;
  refs.unifiedSummary.textContent = pretty(state.unifiedResult);
  showToast(`统一评测完成: ${data.pretrain_readiness?.recommendation || "ok"}`);
}

async function createLiveSession() {
  if (state.live.sessionId) return state.live.sessionId;
  const payload = {
    min_wait_k: 1,
    base_wait_k: Number(refs.baseWaitK.value || 2),
    max_wait_k: Number(refs.maxWaitK.value || 4),
  };
  const data = await apiPost("/api/session/create", payload);
  state.live.sessionId = data.session_id;
  state.live.startWallMs = Date.now();
  setSessionStatus(`会话中 (${state.live.sessionId})`);
  ensurePipelineResultContainer();
  return data.session_id;
}

async function closeLiveSession() {
  if (!state.live.sessionId) return;
  try {
    await apiPost("/api/session/close", { session_id: state.live.sessionId });
  } catch (_e) {
    // ignore close errors
  }
  state.live.sessionId = null;
  setSessionStatus("未启动");
}

async function sendLiveChunk(text) {
  const sessionId = await createLiveSession();
  const ts = Math.max(0, Date.now() - state.live.startWallMs);
  const data = await apiPost("/api/session/chunk", {
    session_id: sessionId,
    text,
    speaker: "expert",
    timestamp_ms: ts,
    is_final: true,
  });

  const emitted = data.emitted_events || [];
  if (emitted.length > 0) {
    appendEventsAndRender(emitted);
  }
  state.pipelineResult.summary = data.session_summary || state.pipelineResult.summary || {};
  updateMetricCards();

  refs.evalSummary.textContent = pretty({
    mode: "live_session",
    events_total: data.events_total,
    updates_emitted: data.session_summary?.updates_emitted,
    latency_e2e_ms: data.session_summary?.latency_e2e_ms,
    boundary_distribution: data.session_summary?.boundary_distribution,
  });
}

function getSpeechRecognitionCtor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

async function startMicrophoneCapture() {
  if (state.live.micActive) {
    showToast("麦克风已经在运行");
    return;
  }
  const SR = getSpeechRecognitionCtor();
  if (!SR) {
    showToast("当前浏览器不支持 Web Speech API");
    return;
  }

  await createLiveSession();
  state.live.micActive = true;
  setSessionStatus(`语音采集中 (${state.live.sessionId})`);
  appendLiveLog(`[system] mic started: ${new Date().toLocaleTimeString()}`);

  const rec = new SR();
  rec.lang = refs.speechLang.value || "zh-CN";
  rec.continuous = true;
  rec.interimResults = true;

  rec.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const r = event.results[i];
      const text = (r[0]?.transcript || "").trim();
      if (!text) continue;
      if (r.isFinal) {
        appendLiveLog(`[final] ${text}`);
        state.live.sendQueue = state.live.sendQueue
          .then(() => sendLiveChunk(text))
          .catch((err) => showToast(`实时发送失败: ${err.message}`));
      } else {
        interim += `${text} `;
      }
    }
    if (interim) {
      setSessionStatus(`语音采集中 (${state.live.sessionId}) · ${interim.trim().slice(0, 18)}...`);
    }
  };

  rec.onerror = (event) => {
    appendLiveLog(`[error] ${event.error || "speech_error"}`);
    showToast(`语音识别错误: ${event.error || "unknown"}`);
  };

  rec.onend = () => {
    if (state.live.micActive) {
      // Auto-resume for robust long sessions.
      try {
        rec.start();
      } catch (_e) {
        // ignore temporary start failures
      }
    }
  };

  state.live.recognition = rec;
  try {
    rec.start();
  } catch (err) {
    state.live.micActive = false;
    showToast(`无法启动麦克风: ${err.message}`);
  }
}

function stopMicrophoneCapture() {
  if (!state.live.micActive) {
    showToast("麦克风未运行");
    return;
  }
  state.live.micActive = false;
  if (state.live.recognition) {
    try {
      state.live.recognition.stop();
    } catch (_e) {
      // ignore
    }
  }
  setSessionStatus(`会话已暂停 (${state.live.sessionId || "-"})`);
  appendLiveLog(`[system] mic stopped: ${new Date().toLocaleTimeString()}`);
}

async function flushLiveSessionAndEvaluate() {
  if (!state.live.sessionId) {
    showToast("没有活跃会话");
    return;
  }
  stopMicrophoneCapture();
  await state.live.sendQueue;
  showToast("正在结束会话并评测...");

  const data = await apiPost("/api/session/flush", {
    session_id: state.live.sessionId,
    close_after_flush: true,
    latency_p95_threshold_ms: 2000,
    flicker_mean_threshold: 6.0,
    mental_map_min: 0.85,
    intent_accuracy_threshold: 0.8,
  });

  if (data.emitted_events?.length) {
    appendEventsAndRender(data.emitted_events);
  }
  state.pipelineResult = data.pipeline;
  state.evaluationResult = data.evaluation;
  refs.evalSummary.textContent = pretty(state.evaluationResult);
  updateMetricCards();
  setSessionStatus("未启动");
  state.live.sessionId = null;

  showToast(`实时会话评测完成: ${state.evaluationResult?.realtime_eval_pass ? "PASS" : "未通过"}`);
}

function bindEvents() {
  document.getElementById("btn-load-sample").addEventListener("click", () => {
    refs.transcriptInput.value = sampleTranscript;
    showToast("示例已加载");
  });
  document.getElementById("btn-run-pipeline").addEventListener("click", async () => {
    try {
      await runPipelineAndRender();
    } catch (err) {
      showToast(`运行失败: ${err.message}`);
    }
  });
  document.getElementById("btn-run-eval").addEventListener("click", async () => {
    try {
      await runRealtimeEvaluation();
    } catch (err) {
      showToast(`评测失败: ${err.message}`);
    }
  });
  document.getElementById("btn-unified-eval").addEventListener("click", async () => {
    try {
      await runUnifiedEval();
    } catch (err) {
      showToast(`统一评测失败: ${err.message}`);
    }
  });

  document.getElementById("btn-start-mic").addEventListener("click", async () => {
    try {
      await startMicrophoneCapture();
    } catch (err) {
      showToast(`麦克风启动失败: ${err.message}`);
    }
  });
  document.getElementById("btn-stop-mic").addEventListener("click", () => {
    stopMicrophoneCapture();
  });
  document.getElementById("btn-flush-live").addEventListener("click", async () => {
    try {
      await flushLiveSessionAndEvaluate();
    } catch (err) {
      showToast(`结束会话失败: ${err.message}`);
    }
  });

  document.getElementById("btn-play").addEventListener("click", startPlayback);
  document.getElementById("btn-pause").addEventListener("click", stopPlayback);
  document.getElementById("btn-reset").addEventListener("click", resetPlayback);
}

async function boot() {
  initSVG();
  refs.transcriptInput.value = sampleTranscript;
  refs.evalSummary.textContent = "{}";
  refs.unifiedSummary.textContent = "{}";
  refs.liveTranscriptLog.value = "";
  setSessionStatus("未启动");
  bindEvents();

  try {
    const resp = await fetch("/api/config");
    const conf = await resp.json();
    if (conf.ok && conf.default_dataset_dir) {
      refs.datasetDir.value = conf.default_dataset_dir;
    }
  } catch (_err) {
    showToast("配置读取失败，使用默认参数");
  }
  window.requestAnimationFrame(animateNodes);
}

boot();
