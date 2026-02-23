"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { RunStatusPill } from "@/components/run-status-pill";
import { TerminalView } from "@/components/terminal-view";
import { fetchService, fetchServiceRuns, runService } from "@/lib/api";
import { Run, Service } from "@/lib/types";
import { useRunStream } from "@/lib/use-run-stream";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

type FieldOption = { label: string; value: string };
type FieldSchema = {
  key: string;
  label: string;
  type: "text" | "number" | "date" | "select" | "checkbox";
  required?: boolean;
  default?: unknown;
  helpText?: string;
  options?: FieldOption[];
};

function getFieldsFromSchema(schema: Record<string, unknown> | null): FieldSchema[] {
  if (!schema || typeof schema !== "object") return [];
  const fields = (schema as { fields?: unknown }).fields;
  if (!Array.isArray(fields)) return [];
  return fields.filter((item): item is FieldSchema => Boolean(item && typeof item === "object" && "key" in item && "type" in item));
}

function buildInitialParameters(fields: FieldSchema[]): Record<string, unknown> {
  const initial: Record<string, unknown> = {};
  fields.forEach((field) => {
    if (field.default !== undefined) {
      initial[field.key] = field.default;
      return;
    }
    if (field.type === "checkbox") {
      initial[field.key] = false;
    } else {
      initial[field.key] = "";
    }
  });
  return initial;
}

export default function PortalServicePage() {
  const params = useParams<{ slug: string; serviceId: string }>();
  const slug = params.slug;
  const serviceId = params.serviceId;

  const [token, setToken] = useState(defaultToken);
  const [service, setService] = useState<Service | null>(null);
  const [recentRuns, setRecentRuns] = useState<Run[]>([]);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [currentRunStatus, setCurrentRunStatus] = useState<Run["status"]>("PENDING");
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fields = useMemo(() => getFieldsFromSchema(service?.form_schema_json ?? null), [service?.form_schema_json]);
  const { logs, status: streamStatus, error: streamError } = useRunStream(currentRunId, token);

  const loadService = async () => {
    if (!serviceId) return;
    setLoading(true);
    setError(null);
    try {
      const [serviceResponse, runsResponse] = await Promise.all([fetchService(serviceId, token), fetchServiceRuns(serviceId, token, 12)]);
      setService(serviceResponse);
      setRecentRuns(runsResponse);
      setParameters(buildInitialParameters(getFieldsFromSchema(serviceResponse.form_schema_json)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar servico.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadService().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceId]);

  useEffect(() => {
    if (!currentRunId) return;
    const last = logs[logs.length - 1];
    if (!last) return;
    const message = last.message.toLowerCase();
    if (message.includes("finished successfully")) {
      setCurrentRunStatus("SUCCESS");
      return;
    }
    if (message.includes("failure") || message.includes("exit code")) {
      setCurrentRunStatus("FAILED");
      return;
    }
    setCurrentRunStatus("RUNNING");
  }, [logs, currentRunId]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!service) return;

    setSubmitting(true);
    setError(null);
    try {
      const run = await runService(service.id, { parameters }, token);
      setCurrentRunId(run.run_id);
      setCurrentRunStatus(run.status);
      const updatedRuns = await fetchServiceRuns(service.id, token, 12);
      setRecentRuns(updatedRuns);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao executar servico.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">{service?.title ?? "Servico"}</h2>
        <p className="page-subtitle">{service?.description ?? "Preencha os parametros e clique em Executar."}</p>
        <p className="helper-text">
          <Link href={`/portal/${slug}`} style={{ color: "#8bb4ff" }}>
            Voltar para servicos
          </Link>
        </p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" type="button" onClick={() => loadService()}>
            Recarregar
          </button>
          {currentRunId ? <RunStatusPill status={currentRunStatus} /> : null}
        </div>
        {loading ? <p className="helper-text">Carregando servico...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
        {streamError ? <p className="helper-text" style={{ color: "#ffb4b4" }}>{streamError}</p> : null}
      </section>

      <section className="split">
        <form className="card form-grid" onSubmit={onSubmit}>
          <h3 style={{ marginTop: 0 }}>Formulario do Servico</h3>
          {fields.map((field) => (
            <label key={field.key}>
              {field.label}
              {field.type === "select" ? (
                <select
                  value={String(parameters[field.key] ?? "")}
                  onChange={(event) => setParameters((previous) => ({ ...previous, [field.key]: event.target.value }))}
                  required={Boolean(field.required)}
                >
                  <option value="">Selecione...</option>
                  {(field.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : field.type === "checkbox" ? (
                <input
                  type="checkbox"
                  checked={Boolean(parameters[field.key])}
                  onChange={(event) => setParameters((previous) => ({ ...previous, [field.key]: event.target.checked }))}
                />
              ) : (
                <input
                  type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
                  value={String(parameters[field.key] ?? "")}
                  onChange={(event) =>
                    setParameters((previous) => ({
                      ...previous,
                      [field.key]: field.type === "number" ? event.target.value : event.target.value
                    }))
                  }
                  required={Boolean(field.required)}
                />
              )}
              {field.helpText ? <span className="helper-text">{field.helpText}</span> : null}
            </label>
          ))}
          <button className="btn-primary" type="submit" disabled={submitting || !service?.enabled}>
            {submitting ? "Executando..." : "Executar servico"}
          </button>
          {!service?.enabled ? <p className="helper-text">Servico desabilitado pelo administrador.</p> : null}
          {currentRunId ? (
            <p className="helper-text">
              Run atual: <strong>{currentRunId}</strong> | stream: <strong>{streamStatus}</strong>
            </p>
          ) : null}
        </form>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Runs recentes do servico</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Versao</th>
                  <th>Inicio</th>
                  <th>Duracao</th>
                  <th>Artefatos</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.run_id.slice(0, 8)}...</td>
                    <td>
                      <RunStatusPill status={run.status} />
                    </td>
                    <td>{run.robot_version?.version ?? "-"}</td>
                    <td>{run.started_at ? new Date(run.started_at).toLocaleString() : "-"}</td>
                    <td>{run.duration_seconds ?? "-"}</td>
                    <td>
                      {run.artifacts.length > 0
                        ? run.artifacts.map((artifact) => (
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
                        : "-"}
                    </td>
                  </tr>
                ))}
                {recentRuns.length === 0 ? (
                  <tr>
                    <td colSpan={6}>Nenhuma execucao registrada para este servico.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="card" style={{ marginTop: 16 }}>
        <h3 style={{ marginTop: 0 }}>Terminal ao vivo</h3>
        <TerminalView logs={logs} />
      </section>
    </>
  );
}
