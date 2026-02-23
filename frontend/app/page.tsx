"use client";

import { useEffect, useMemo, useState } from "react";

import { PerformanceChart } from "@/components/performance-chart";
import { RunStatusPill } from "@/components/run-status-pill";
import { StatCard } from "@/components/stat-card";
import { StatusChart } from "@/components/status-chart";
import { fetchAlerts, fetchRobots, fetchRuns, resolveAlert } from "@/lib/api";
import { AlertEvent, Run } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

function summarizeRuns(runs: Run[]) {
  const total = runs.length;
  const running = runs.filter((run) => run.status === "RUNNING").length;
  const success = runs.filter((run) => run.status === "SUCCESS").length;
  const failed = runs.filter((run) => run.status === "FAILED").length;
  const avgDuration =
    runs.filter((run) => typeof run.duration_seconds === "number").reduce((acc, run) => acc + (run.duration_seconds ?? 0), 0) /
    Math.max(
      1,
      runs.filter((run) => typeof run.duration_seconds === "number").length
    );

  return {
    total,
    running,
    success,
    failed,
    avgDuration: Number(avgDuration.toFixed(2))
  };
}

export default function DashboardPage() {
  const [token, setToken] = useState(defaultToken);
  const [robotsTotal, setRobotsTotal] = useState(0);
  const [runs, setRuns] = useState<Run[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const metrics = useMemo(() => summarizeRuns(runs), [runs]);

  const durationData = useMemo(
    () =>
      runs.slice(0, 12).reverse().map((run, index) => ({
        label: `Run ${index + 1}`,
        duration: run.duration_seconds ?? 0
      })),
    [runs]
  );

  const statusData = useMemo(
    () => [
      { name: "PENDING", value: runs.filter((run) => run.status === "PENDING").length },
      { name: "RUNNING", value: metrics.running },
      { name: "SUCCESS", value: metrics.success },
      { name: "FAILED", value: metrics.failed }
    ],
    [metrics.failed, metrics.running, metrics.success, runs]
  );

  const alertCards = useMemo(() => {
    const openAlerts = alerts.filter((alert) => !alert.resolved_at);
    return {
      late: openAlerts.filter((alert) => alert.type === "LATE").length,
      critical: openAlerts.filter((alert) => alert.severity === "CRITICAL").length,
      failureStreak: openAlerts.filter((alert) => alert.type === "FAILURE_STREAK").length,
      queue: openAlerts.filter((alert) => alert.type === "QUEUE_BACKLOG").length
    };
  }, [alerts]);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const [robotsResponse, runsResponse, alertsResponse] = await Promise.all([
        fetchRobots(token),
        fetchRuns(token),
        fetchAlerts(token, { status: "open", limit: 100 })
      ]);
      setRobotsTotal(robotsResponse.total);
      setRuns(runsResponse.items);
      setAlerts(alertsResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dashboard.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onResolveAlert = async (alertId: string) => {
    try {
      await resolveAlert(alertId, token);
      await loadDashboard();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao resolver alerta.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Dashboard Operacional</h2>
        <p className="page-subtitle">Monitoramento executivo de automacao, scheduler, SLA e alertas corporativos.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" onClick={() => loadDashboard()}>
            Recarregar
          </button>
        </div>
        {loading ? <p className="helper-text">Carregando dashboard...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="grid cols-4">
        <StatCard label="Robos registrados" value={robotsTotal} />
        <StatCard label="Runs totais" value={metrics.total} />
        <StatCard label="Runs em execucao" value={metrics.running} />
        <StatCard label="Duracao media (s)" value={metrics.avgDuration} />
      </section>

      <section className="grid cols-4" style={{ marginTop: 16 }}>
        <StatCard label="Atrasados" value={alertCards.late} />
        <StatCard label="Criticos" value={alertCards.critical} />
        <StatCard label="Falha recorrente" value={alertCards.failureStreak} />
        <StatCard label="Fila alta" value={alertCards.queue} />
      </section>

      <section className="grid cols-2" style={{ marginTop: 16 }}>
        <PerformanceChart data={durationData} />
        <StatusChart data={statusData} />
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Alerta</th>
                <th>Tipo</th>
                <th>Severidade</th>
                <th>Robo</th>
                <th>Criado em</th>
                <th>Acao</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>{alert.message}</td>
                  <td>{alert.type}</td>
                  <td>{alert.severity}</td>
                  <td>{alert.robot_id.slice(0, 8)}...</td>
                  <td>{new Date(alert.created_at).toLocaleString()}</td>
                  <td>
                    <button className="btn-secondary" onClick={() => onResolveAlert(alert.id)}>
                      Resolver
                    </button>
                  </td>
                </tr>
              ))}
              {alerts.length === 0 ? (
                <tr>
                  <td colSpan={6}>Nenhum alerta aberto no momento.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section style={{ marginTop: 16 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Status</th>
                <th>Trigger</th>
                <th>Tentativa</th>
                <th>Inicio</th>
                <th>Fim</th>
                <th>Duracao (s)</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 8).map((run) => (
                <tr key={run.run_id}>
                  <td>{run.run_id.slice(0, 8)}...</td>
                  <td>
                    <RunStatusPill status={run.status} />
                  </td>
                  <td>{run.trigger_type}</td>
                  <td>{run.attempt}</td>
                  <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                  <td>{run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</td>
                  <td>{run.duration_seconds ?? "-"}</td>
                </tr>
              ))}
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={7}>Nenhum dado de execucao disponivel.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
