"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { cancelRun, executeRun, fetchRobots, fetchRun } from "@/lib/api";
import { Robot } from "@/lib/types";
import { useRunStream } from "@/lib/use-run-stream";

import { RunStatusPill } from "@/components/run-status-pill";
import { TerminalView } from "@/components/terminal-view";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export default function ExecutionsPage() {
  const [token, setToken] = useState(defaultToken);
  const [robots, setRobots] = useState<Robot[]>([]);
  const [robotId, setRobotId] = useState("");
  const [robotVersionId, setRobotVersionId] = useState("");
  const [runtimeArgsRaw, setRuntimeArgsRaw] = useState("");
  const [runtimeEnvRaw, setRuntimeEnvRaw] = useState("");
  const [envName, setEnvName] = useState<"PROD" | "HML" | "TEST">("PROD");
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [currentRunStatus, setCurrentRunStatus] = useState<string>("PENDING");
  const [error, setError] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isCanceling, setIsCanceling] = useState(false);

  const selectedRobot = useMemo(() => robots.find((robot) => robot.id === robotId), [robots, robotId]);

  const runtimeArguments = useMemo(
    () =>
      runtimeArgsRaw
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean),
    [runtimeArgsRaw]
  );

  const runtimeEnv = useMemo(() => {
    const result: Record<string, string> = {};
    runtimeEnvRaw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .forEach((line) => {
        const [key, ...rest] = line.split("=");
        if (key && rest.length > 0) {
          result[key.trim()] = rest.join("=").trim();
        }
      });
    return result;
  }, [runtimeEnvRaw]);

  const { logs, status: streamStatus, error: streamError } = useRunStream(currentRunId, token);

  useEffect(() => {
    if (!currentRunId) return;
    const last = logs[logs.length - 1];
    if (!last) return;
    const msg = last.message.toLowerCase();
    if (msg.includes("finished successfully")) {
      setCurrentRunStatus("SUCCESS");
      return;
    }
    if (msg.includes("failure") || msg.includes("exit code")) {
      setCurrentRunStatus("FAILED");
      return;
    }
    if (msg.includes("execution canceled by user") || msg.includes("marked as canceled")) {
      setCurrentRunStatus("CANCELED");
      return;
    }
    if (msg.includes("timeout")) {
      setCurrentRunStatus("FAILED");
      return;
    }
    if (["SUCCESS", "FAILED", "CANCELED"].includes(currentRunStatus)) return;
    setCurrentRunStatus("RUNNING");
  }, [logs, currentRunId, currentRunStatus]);

  useEffect(() => {
    if (!currentRunId) return;
    const terminal = ["SUCCESS", "FAILED", "CANCELED"].includes(currentRunStatus);
    if (terminal) return;

    const interval = setInterval(async () => {
      try {
        const run = await fetchRun(currentRunId, token);
        setCurrentRunStatus(run.status);
      } catch {
        // noop
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentRunId, currentRunStatus, token]);

  const loadRobots = async () => {
    try {
      const response = await fetchRobots(token);
      setRobots(response.items);
      if (!robotId && response.items[0]) {
        setRobotId(response.items[0].id);
        const active = response.items[0].versions.find((version) => version.is_active);
        setRobotVersionId(active?.id ?? response.items[0].versions[0]?.id ?? "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load robots.");
    }
  };

  useEffect(() => {
    loadRobots().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedRobot) return;
    const found = selectedRobot.versions.find((version) => version.id === robotVersionId);
    if (!found) {
      const active = selectedRobot.versions.find((version) => version.is_active);
      setRobotVersionId(active?.id ?? selectedRobot.versions[0]?.id ?? "");
    }
  }, [selectedRobot, robotVersionId]);

  const onExecute = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!robotId) return;
    setError(null);
    setIsExecuting(true);
    try {
      const run = await executeRun(
        robotId,
        {
          version_id: robotVersionId || undefined,
          robot_version_id: robotVersionId || undefined,
          runtime_arguments: runtimeArguments,
          runtime_env: runtimeEnv,
          env_name: envName
        },
        token
      );
      setCurrentRunId(run.run_id);
      setCurrentRunStatus(run.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger execution.");
    } finally {
      setIsExecuting(false);
    }
  };

  const onCancelRun = async () => {
    if (!currentRunId) return;
    if (!window.confirm("Confirmar cancelamento da execucao em andamento?")) return;

    setIsCanceling(true);
    setError(null);
    try {
      const canceled = await cancelRun(currentRunId, token);
      setCurrentRunStatus(canceled.status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao solicitar cancelamento.");
    } finally {
      setIsCanceling(false);
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Remote Execution</h2>
        <p className="page-subtitle">Execute robots and stream logs in real time.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <form className="form-grid" onSubmit={onExecute}>
          <div className="split">
            <label>
              API token (Bearer)
              <input value={token} onChange={(event) => setToken(event.target.value)} />
            </label>
            <label>
              Robot
              <select value={robotId} onChange={(event) => setRobotId(event.target.value)}>
                {robots.map((robot) => (
                  <option key={robot.id} value={robot.id}>
                    {robot.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="split">
            <label>
              Version
              <select value={robotVersionId} onChange={(event) => setRobotVersionId(event.target.value)}>
                {(selectedRobot?.versions ?? []).map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.version} ({version.channel}) {version.is_active ? "[active]" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Ambiente
              <select value={envName} onChange={(event) => setEnvName(event.target.value as "PROD" | "HML" | "TEST")}>
                <option value="PROD">PROD</option>
                <option value="HML">HML</option>
                <option value="TEST">TEST</option>
              </select>
            </label>
            <label>
              Runtime arguments (comma-separated)
              <input value={runtimeArgsRaw} onChange={(event) => setRuntimeArgsRaw(event.target.value)} placeholder="--input=dataset1,--retry=2" />
            </label>
          </div>
          <label>
            Runtime environment (KEY=VALUE per line)
            <textarea value={runtimeEnvRaw} onChange={(event) => setRuntimeEnvRaw(event.target.value)} />
          </label>
          <div className="toolbar">
            <button className="btn-primary" type="submit" disabled={isExecuting}>
              {isExecuting ? "Executing..." : "Execute robot"}
            </button>
            <button className="btn-secondary" type="button" onClick={() => loadRobots()}>
              Refresh robots
            </button>
            {currentRunId && currentRunStatus === "RUNNING" ? (
              <button className="btn-secondary" type="button" onClick={onCancelRun} disabled={isCanceling}>
                {isCanceling ? "Cancelando..." : "Cancelar Execucao"}
              </button>
            ) : null}
            {currentRunId ? <RunStatusPill status={currentRunStatus} /> : null}
          </div>
          {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
          {streamError ? <p className="helper-text" style={{ color: "#ffb4b4" }}>{streamError}</p> : null}
          {currentRunId ? (
            <p className="helper-text">
              Current run: <strong>{currentRunId}</strong> | stream: <strong>{streamStatus}</strong>
            </p>
          ) : null}
        </form>
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Live terminal</h3>
        <TerminalView logs={logs} />
      </section>
    </>
  );
}
