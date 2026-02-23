import { PerformanceChart } from "@/components/performance-chart";
import { RunStatusPill } from "@/components/run-status-pill";
import { StatCard } from "@/components/stat-card";
import { StatusChart } from "@/components/status-chart";
import { fetchRobots, fetchRuns } from "@/lib/api";
import { Run } from "@/lib/types";

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

export default async function DashboardPage() {
  const [robotsResponse, runsResponse] = await Promise.all([
    fetchRobots().catch(() => ({ items: [], total: 0 })),
    fetchRuns().catch(() => ({ items: [], total: 0 }))
  ]);

  const metrics = summarizeRuns(runsResponse.items);
  const durationData = runsResponse.items.slice(0, 12).reverse().map((run, index) => ({
    label: `Run ${index + 1}`,
    duration: run.duration_seconds ?? 0
  }));
  const statusData = [
    { name: "PENDING", value: runsResponse.items.filter((run) => run.status === "PENDING").length },
    { name: "RUNNING", value: metrics.running },
    { name: "SUCCESS", value: metrics.success },
    { name: "FAILED", value: metrics.failed }
  ];

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Dashboard Operacional</h2>
        <p className="page-subtitle">
          Monitoramento executivo de execução de robôs, estabilidade e throughput da automação.
        </p>
      </header>

      <section className="grid cols-4">
        <StatCard label="Robôs registrados" value={robotsResponse.total} />
        <StatCard label="Runs totais" value={metrics.total} />
        <StatCard label="Runs em execução" value={metrics.running} />
        <StatCard label="Duração média (s)" value={metrics.avgDuration} />
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
                <th>Run ID</th>
                <th>Status</th>
                <th>Início</th>
                <th>Fim</th>
                <th>Duração (s)</th>
              </tr>
            </thead>
            <tbody>
              {runsResponse.items.slice(0, 8).map((run) => (
                <tr key={run.run_id}>
                  <td>{run.run_id.slice(0, 8)}...</td>
                  <td>
                    <RunStatusPill status={run.status} />
                  </td>
                  <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                  <td>{run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</td>
                  <td>{run.duration_seconds ?? "-"}</td>
                </tr>
              ))}
              {runsResponse.items.length === 0 ? (
                <tr>
                  <td colSpan={5}>Nenhum dado de execução disponível (verifique token de API no frontend).</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
