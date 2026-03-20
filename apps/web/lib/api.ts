"use client";

import { z } from "zod";

import {
  datasetSplitSummarySchema,
  datasetVersionSummarySchema,
  reportDetailSchema,
  reportSummarySchema,
  realtimeSessionSchema,
  realtimeSnapshotSchema,
  runArtifactSchema,
  runJobSchema,
  sampleDetailSchema,
  sampleListItemSchema,
  studySessionSchema,
  studyTaskSchema,
} from "@stream2graph/contracts";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";

export function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

async function request<TSchema extends z.ZodTypeAny>(
  path: string,
  schema: TSchema,
  init?: RequestInit,
): Promise<z.infer<TSchema>> {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const text = await response.text();
  const raw = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(raw.detail || raw.error || `HTTP ${response.status}`);
  }
  return schema.parse(raw);
}

export const api = {
  health: async () => request("/api/health", z.record(z.any())),
  login: async (payload: { username: string; password: string }) =>
    request("/api/v1/auth/login", z.object({ username: z.string(), display_name: z.string() }), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: async () => request("/api/v1/auth/logout", z.object({ ok: z.boolean() }), { method: "POST" }),
  me: async () => request("/api/v1/auth/me", z.object({ username: z.string(), display_name: z.string() })),
  listDatasets: async () => request("/api/v1/catalog/datasets", z.array(datasetVersionSummarySchema)),
  listSplits: async (slug: string) =>
    request(`/api/v1/catalog/datasets/${slug}/splits`, z.array(datasetSplitSummarySchema)),
  listSamples: async (slug: string, split: string, search = "", offset = 0, limit = 25) =>
    request(
      `/api/v1/catalog/datasets/${slug}/samples?split=${split}&search=${encodeURIComponent(search)}&offset=${offset}&limit=${limit}`,
      z.array(sampleListItemSchema),
    ),
  getSample: async (slug: string, split: string, sampleId: string) =>
    request(
      `/api/v1/catalog/datasets/${slug}/samples/${sampleId}?split=${split}`,
      sampleDetailSchema,
    ),
  listRealtimeSessions: async () => request("/api/v1/realtime/sessions", z.array(realtimeSessionSchema)),
  createRealtimeSession: async (payload: Record<string, unknown>) =>
    request("/api/v1/realtime/sessions", realtimeSessionSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRealtimeSession: async (sessionId: string) =>
    request(`/api/v1/realtime/sessions/${sessionId}`, realtimeSessionSchema),
  addRealtimeChunk: async (sessionId: string, payload: Record<string, unknown>) =>
    request(
      `/api/v1/realtime/sessions/${sessionId}/chunks`,
      z.object({
        ok: z.boolean(),
        session_id: z.string(),
        emitted_events: z.array(z.record(z.any())),
        pipeline: z.record(z.any()),
        evaluation: z.record(z.any()),
      }),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  snapshotRealtime: async (sessionId: string) =>
    request(`/api/v1/realtime/sessions/${sessionId}/snapshot`, realtimeSnapshotSchema, {
      method: "POST",
    }),
  flushRealtime: async (sessionId: string) =>
    request(`/api/v1/realtime/sessions/${sessionId}/flush`, realtimeSnapshotSchema, {
      method: "POST",
    }),
  closeRealtime: async (sessionId: string) =>
    request(`/api/v1/realtime/sessions/${sessionId}/close`, z.object({ ok: z.boolean(), session_id: z.string(), closed: z.boolean() }), {
      method: "POST",
    }),
  saveRealtimeReport: async (sessionId: string) =>
    request(`/api/v1/realtime/sessions/${sessionId}/report`, z.object({ ok: z.boolean(), report_id: z.string() }), {
      method: "POST",
    }),
  listRuns: async () => request("/api/v1/runs", z.array(runJobSchema)),
  createSampleCompareRun: async (payload: Record<string, unknown>) =>
    request("/api/v1/runs/sample-compare", runJobSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createBenchmarkRun: async (payload: Record<string, unknown>) =>
    request("/api/v1/runs/benchmark-suite", runJobSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getRun: async (runId: string) => request(`/api/v1/runs/${runId}`, runJobSchema),
  listRunArtifacts: async (runId: string) =>
    request(`/api/v1/runs/${runId}/artifacts`, z.array(runArtifactSchema)),
  listStudyTasks: async () => request("/api/v1/studies/tasks", z.array(studyTaskSchema)),
  createStudyTask: async (payload: Record<string, unknown>) =>
    request("/api/v1/studies/tasks", studyTaskSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listStudySessions: async () => request("/api/v1/studies/sessions", z.array(studySessionSchema)),
  createStudySession: async (taskId: string, payload: Record<string, unknown>) =>
    request(`/api/v1/studies/tasks/${taskId}/sessions`, studySessionSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getParticipantSession: async (code: string) =>
    request(`/api/v1/studies/participant/${code}`, studySessionSchema),
  startParticipantSession: async (code: string) =>
    request(`/api/v1/studies/participant/${code}/start`, studySessionSchema, {
      method: "POST",
    }),
  logParticipantEvent: async (code: string, payload: Record<string, unknown>) =>
    request(`/api/v1/studies/participant/${code}/events`, z.object({ ok: z.boolean() }), {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  autosaveParticipant: async (code: string, payload: Record<string, unknown>) =>
    request(`/api/v1/studies/participant/${code}/autosave`, studySessionSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  submitParticipant: async (code: string, payload: Record<string, unknown>) =>
    request(`/api/v1/studies/participant/${code}/submit`, studySessionSchema, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  saveSurvey: async (code: string, payload: Record<string, unknown>) =>
    request(
      `/api/v1/studies/participant/${code}/survey`,
      z.object({ study_session_id: z.string(), payload: z.record(z.any()), submitted_at: z.string() }),
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  listReports: async () => request("/api/v1/reports", z.array(reportSummarySchema)),
  getReport: async (reportId: string) => request(`/api/v1/reports/${reportId}`, reportDetailSchema),
};

export function subscribeRun(runId: string, onMessage: (payload: z.infer<typeof runJobSchema>) => void) {
  const source = new EventSource(apiUrl(`/api/v1/runs/stream/events?run_id=${runId}`), {
    withCredentials: true,
  });
  source.onmessage = (event) => {
    const parsed = runJobSchema.parse(JSON.parse(event.data));
    onMessage(parsed);
    if (parsed.status === "succeeded" || parsed.status === "failed" || parsed.status === "cancelled") {
      source.close();
    }
  };
  return source;
}
