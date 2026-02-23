"use client";

import { useEffect, useMemo, useState } from "react";

import { RunStatusPill } from "@/components/run-status-pill";
import { cancelRun, fetchOpsStatus, fetchRuns, fetchWorkers, pauseWorker, resumeWorker } from "@/lib/api";
import { OpsStatus, Run, Worker } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

const workerStatusClass: Record<Worker["status"], string> = {
  RUNNING: "success",
  PAUSED: "pending",
  STOPPED: "failed"
};

export default function OperationsAdminPage() {
  const [token, setToken] = useState(defaultToken);
  const [opsStatus, setOpsStatus] = useState<OpsStatus | null>(null);
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [runningRuns, setRunningRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const staleWorkerIds = useMemo(() => {
    const now = Date.now();
    return new Set(
      workers
        .filter((worker) => now - new Date(worker.last_heartbeat).getTime() > 60_000)
        .map((worker) => worker.id)
    );
  }, [workers]);

  const refreshData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusData, workerData, runsData] = await Promise.all([
        fetchOpsStatus(token),
        fetchWorkers(token),
        fetchRuns(token, { status: "RUNNING" })
      ]);
      setOpsStatus(statusData);
      setWorkers(workerData);
      setRunningRuns(runsData.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados operacionais.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      refreshData().catch(() => undefined);
    }, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const onPause = async (workerId: string) => {
    try {
      await pauseWorker(workerId, token);
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao pausar worker.");
    }
  };

  const onResume = async (workerId: string) => {
    try {
      await resumeWorker(workerId, token);
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao retomar worker.");
    }
  };

  const onCancelRun = async (runId: string) => {
    if (!window.confirm("Confirmar cancelamento deste run em andamento?")) return;
    try {
      await cancelRun(runId, token);
      await refreshData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao cancelar run.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Operacoes</h2>
        <p className="page-subtitle">Controle de workers, fila e execucoes em andamento.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            API token (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" onClick={() => refreshData()}>
            Atualizar
          </button>
        </div>
        {loading ? <p className="helper-text">Carregando...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="card">
          <p className="card-label">Workers</p>
          <p className="card-value">{opsStatus?.total_workers ?? 0}</p>
          <p className="card-subtitle">Total registrados</p>
        </div>
        <div className="card">
          <p className="card-label">Workers Running</p>
          <p className="card-value">{opsStatus?.workers_running ?? 0}</p>
          <p className="card-subtitle">Consumindo fila</p>
        </div>
        <div className="card">
          <p className="card-label">Workers Paused</p>
          <p className="card-value">{opsStatus?.workers_paused ?? 0}</p>
          <p className="card-subtitle">Temporariamente pausados</p>
        </div>
        <div className="card">
          <p className="card-label">Queue Depth</p>
          <p className="card-value">{opsStatus?.queue_depth ?? 0}</p>
          <p className="card-subtitle">Jobs pendentes</p>
        </div>
      </section>

      <section className="grid cols-4" style={{ marginBottom: 16 }}>
        <div className="card">
          <p className="card-label">Runs Running</p>
          <p className="card-value">{opsStatus?.runs_running ?? 0}</p>
          <p className="card-subtitle">Execucao ativa</p>
        </div>
        <div className="card">
          <p className="card-label">Failed (1h)</p>
          <p className="card-value">{opsStatus?.runs_failed_last_hour ?? 0}</p>
          <p className="card-subtitle">Falhas recentes</p>
        </div>
        <div className="card">
          <p className="card-label">Uptime (s)</p>
          <p className="card-value">{opsStatus?.uptime_seconds ?? 0}</p>
          <p className="card-subtitle">Tempo online da API</p>
        </div>
      </section>

      <section className="table-wrap" style={{ marginBottom: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Worker ID</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Heartbeat</th>
              <th>Version</th>
              <th>Acoes</th>
            </tr>
          </thead>
          <tbody>
            {workers.map((worker) => (
              <tr key={worker.id}>
                <td>{worker.id.slice(0, 8)}...</td>
                <td>{worker.hostname}</td>
                <td>
                  <span className={`status-pill ${workerStatusClass[worker.status]}`}>{worker.status}</span>
                  {staleWorkerIds.has(worker.id) ? <span style={{ marginLeft: 8, color: "#ff9a9a" }}>stale</span> : null}
                </td>
                <td>{new Date(worker.last_heartbeat).toLocaleString()}</td>
                <td>{worker.version ?? "-"}</td>
                <td>
                  {worker.status === "RUNNING" ? (
                    <button className="btn-secondary" onClick={() => onPause(worker.id)}>
                      Pause
                    </button>
                  ) : (
                    <button className="btn-secondary" onClick={() => onResume(worker.id)}>
                      Resume
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {workers.length === 0 ? (
              <tr>
                <td colSpan={6}>Nenhum worker registrado.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>

      <section className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Robot</th>
              <th>Version</th>
              <th>Status</th>
              <th>Trigger</th>
              <th>Attempt</th>
              <th>Started</th>
              <th>Acoes</th>
            </tr>
          </thead>
          <tbody>
            {runningRuns.map((run) => (
              <tr key={run.run_id}>
                <td>{run.run_id.slice(0, 8)}...</td>
                <td>{run.robot_id.slice(0, 8)}...</td>
                <td>{run.robot_version?.version ?? run.robot_version_id.slice(0, 8)}</td>
                <td><RunStatusPill status={run.status} /></td>
                <td>{run.trigger_type}</td>
                <td>{run.attempt}</td>
                <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                <td>
                  <button className="btn-secondary" onClick={() => onCancelRun(run.run_id)}>
                    Cancelar
                  </button>
                </td>
              </tr>
            ))}
            {runningRuns.length === 0 ? (
              <tr>
                <td colSpan={8}>Nenhum run em andamento.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </>
  );
}
