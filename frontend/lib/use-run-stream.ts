"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchRunLogs, wsLogsUrl } from "@/lib/api";
import { RunLog } from "@/lib/types";

type StreamState = {
  logs: RunLog[];
  status: "idle" | "connecting" | "connected" | "disconnected" | "error";
  error: string | null;
};

function normalizeWsMessage(raw: string): RunLog | null {
  try {
    const parsed = JSON.parse(raw);
    return {
      id: parsed.id ?? Date.now(),
      run_id: parsed.run_id,
      timestamp: parsed.timestamp,
      level: parsed.level,
      message: parsed.message
    };
  } catch {
    return null;
  }
}

export function useRunStream(runId: string | null, token?: string): StreamState {
  const [logs, setLogs] = useState<RunLog[]>([]);
  const [status, setStatus] = useState<StreamState["status"]>("idle");
  const [error, setError] = useState<string | null>(null);

  const enabled = useMemo(() => Boolean(runId), [runId]);

  useEffect(() => {
    if (!enabled || !runId) {
      setStatus("idle");
      setLogs([]);
      setError(null);
      return;
    }

    let socket: WebSocket | null = null;
    let closedManually = false;

    const hydrateLogs = async () => {
      try {
        const initialLogs = await fetchRunLogs(runId, token);
        setLogs(initialLogs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Falha ao carregar logs iniciais.");
      }
    };

    hydrateLogs().catch(() => undefined);

    setStatus("connecting");
    socket = new WebSocket(wsLogsUrl(runId, token));

    socket.onopen = () => {
      setStatus("connected");
      setError(null);
    };

    socket.onmessage = (event) => {
      const parsed = normalizeWsMessage(event.data);
      if (!parsed) return;
      setLogs((prev) => [...prev, parsed]);
    };

    socket.onerror = () => {
      setStatus("error");
      setError("Conexão WebSocket com logs falhou.");
    };

    socket.onclose = () => {
      if (!closedManually) {
        setStatus("disconnected");
      }
    };

    return () => {
      closedManually = true;
      socket?.close();
    };
  }, [enabled, runId, token]);

  return { logs, status, error };
}
