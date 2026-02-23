"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { RunStatusPill } from "@/components/run-status-pill";
import { fetchRuns } from "@/lib/api";
import { Run } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function RunsHistoryPage() {
  const [token, setToken] = useState(defaultToken);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [triggerFilter, setTriggerFilter] = useState<"" | "MANUAL" | "SCHEDULED" | "RETRY">("");

  const loadRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchRuns(token, { triggerType: triggerFilter || undefined });
      setRuns(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load runs history.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRuns().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerFilter]);

  const durationByRobot = useMemo(() => {
    const map = new Map<string, { label: string; duration: number }>();
    runs.forEach((run) => {
      const current = map.get(run.robot_id) ?? { label: run.robot_id.slice(0, 6), duration: 0 };
      current.duration += run.duration_seconds ?? 0;
      map.set(run.robot_id, current);
    });
    return Array.from(map.values()).slice(0, 10);
  }, [runs]);

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Runs History</h2>
        <p className="page-subtitle">Execution timeline with version traceability, trigger type and retries.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            API token (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <label>
            Trigger filter
            <select value={triggerFilter} onChange={(event) => setTriggerFilter(event.target.value as "" | "MANUAL" | "SCHEDULED" | "RETRY") }>
              <option value="">All</option>
              <option value="MANUAL">MANUAL</option>
              <option value="SCHEDULED">SCHEDULED</option>
              <option value="RETRY">RETRY</option>
            </select>
          </label>
          <button className="btn-secondary" onClick={() => loadRuns()}>
            Refresh history
          </button>
        </div>
        {loading ? <p className="helper-text">Loading history...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="chart-card" style={{ marginBottom: 16 }}>
        <h3>Accumulated duration by robot (s)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={durationByRobot}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a3852" />
            <XAxis dataKey="label" stroke="#9fb4d9" />
            <YAxis stroke="#9fb4d9" />
            <Tooltip />
            <Bar dataKey="duration" fill="#4a7de2" />
          </BarChart>
        </ResponsiveContainer>
      </section>

      <section className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Servico</th>
              <th>Robot</th>
              <th>Status</th>
              <th>Version</th>
              <th>Trigger</th>
              <th>Attempt</th>
              <th>Started</th>
              <th>Finished</th>
              <th>Duration (s)</th>
              <th>Error</th>
              <th>Canceled By</th>
              <th>Artifacts</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.run_id}>
                <td>{run.run_id.slice(0, 8)}...</td>
                <td>{run.service?.title ?? "-"}</td>
                <td>{run.robot_id.slice(0, 8)}...</td>
                <td>
                  <RunStatusPill status={run.status} />
                </td>
                <td>
                  {run.robot_version ? (
                    <Link href={`/robots/${run.robot_id}?versionId=${run.robot_version.id}`} style={{ color: "#8bb4ff" }}>
                      {run.robot_version.version}
                    </Link>
                  ) : (
                    run.robot_version_id.slice(0, 8)
                  )}
                </td>
                <td>{run.trigger_type}</td>
                <td>{run.attempt}</td>
                <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                <td>{run.finished_at ? new Date(run.finished_at).toLocaleString() : "-"}</td>
                <td>{run.duration_seconds ?? "-"}</td>
                <td>{run.error_message ?? "-"}</td>
                <td>{run.canceled_by ? `${run.canceled_by.slice(0, 8)}...` : "-"}</td>
                <td>
                  {run.artifacts.length > 0 ? (
                    run.artifacts.map((artifact) => (
                      <a
                        key={artifact.id}
                        href={`${apiBase}/runs/${run.run_id}/artifacts/${artifact.id}/download`}
                        target="_blank"
                        rel="noreferrer"
                        style={{ display: "block", color: "#8bb4ff" }}
                      >
                        {artifact.artifact_name}
                      </a>
                    ))
                  ) : (
                    <span>-</span>
                  )}
                </td>
              </tr>
            ))}
            {runs.length === 0 ? (
              <tr>
                <td colSpan={13}>No runs available.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </>
  );
}
