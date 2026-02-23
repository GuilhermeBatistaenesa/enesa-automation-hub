"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import {
  activateRobotVersion,
  createRobotSchedule,
  createRobotSla,
  deleteRobotEnvVar,
  deleteRobotSchedule,
  fetchRobotEnvVars,
  fetchRobotSchedule,
  fetchRobotSla,
  fetchRobotVersions,
  publishRobotVersion,
  upsertRobotEnvVars,
  updateRobotSchedule,
  updateRobotSla
} from "@/lib/api";
import { RobotEnvVar, RobotVersion, Schedule, SlaRule } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

type TabKey = "versions" | "schedule" | "sla" | "config";

export default function RobotDetailsPage() {
  const params = useParams<{ robotId: string }>();
  const searchParams = useSearchParams();
  const robotId = params.robotId;
  const highlightedVersionId = searchParams.get("versionId");

  const [activeTab, setActiveTab] = useState<TabKey>("versions");
  const [token, setToken] = useState(defaultToken);
  const [versions, setVersions] = useState<RobotVersion[]>([]);
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [sla, setSla] = useState<SlaRule | null>(null);
  const [selectedEnv, setSelectedEnv] = useState<"PROD" | "HML" | "TEST">("PROD");
  const [envVars, setEnvVars] = useState<RobotEnvVar[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);

  const [version, setVersion] = useState("");
  const [channel, setChannel] = useState<"stable" | "beta" | "hotfix">("stable");
  const [changelog, setChangelog] = useState("");
  const [entrypointPath, setEntrypointPath] = useState("main.py");
  const [entrypointType, setEntrypointType] = useState<"PYTHON" | "EXE">("PYTHON");
  const [artifactFile, setArtifactFile] = useState<File | null>(null);
  const [publishActivate, setPublishActivate] = useState(true);
  const [envKey, setEnvKey] = useState("");
  const [envValue, setEnvValue] = useState("");
  const [envIsSecret, setEnvIsSecret] = useState(false);

  const [scheduleForm, setScheduleForm] = useState({
    enabled: true,
    cron_expr: "*/15 * * * *",
    timezone: "America/Sao_Paulo",
    window_start: "",
    window_end: "",
    max_concurrency: 1,
    timeout_seconds: 3600,
    retry_count: 0,
    retry_backoff_seconds: 60
  });

  const [slaForm, setSlaForm] = useState({
    expected_run_every_minutes: 60,
    expected_daily_time: "",
    late_after_minutes: 15,
    alert_on_failure: true,
    alert_on_late: true,
    notify_channels_json: "{}"
  });

  const activeVersion = useMemo(() => versions.find((item) => item.is_active), [versions]);
  const requiredEnvKeys = useMemo(() => activeVersion?.required_env_keys_json ?? [], [activeVersion]);
  const missingRequiredKeys = useMemo(() => {
    const available = new Set(envVars.map((item) => item.key));
    return requiredEnvKeys.filter((key) => !available.has(key));
  }, [envVars, requiredEnvKeys]);

  const loadAll = async () => {
    if (!robotId) return;
    setLoading(true);
    setError(null);
    try {
      const versionsResponse = await fetchRobotVersions(robotId, token);
      setVersions(versionsResponse);
      const envResponse = await fetchRobotEnvVars(robotId, selectedEnv, token);
      setEnvVars(envResponse);

      try {
        const scheduleResponse = await fetchRobotSchedule(robotId, token);
        setSchedule(scheduleResponse);
        setScheduleForm({
          enabled: scheduleResponse.enabled,
          cron_expr: scheduleResponse.cron_expr,
          timezone: scheduleResponse.timezone,
          window_start: scheduleResponse.window_start ?? "",
          window_end: scheduleResponse.window_end ?? "",
          max_concurrency: scheduleResponse.max_concurrency,
          timeout_seconds: scheduleResponse.timeout_seconds,
          retry_count: scheduleResponse.retry_count,
          retry_backoff_seconds: scheduleResponse.retry_backoff_seconds
        });
      } catch {
        setSchedule(null);
      }

      try {
        const slaResponse = await fetchRobotSla(robotId, token);
        setSla(slaResponse);
        setSlaForm({
          expected_run_every_minutes: slaResponse.expected_run_every_minutes ?? 0,
          expected_daily_time: slaResponse.expected_daily_time ?? "",
          late_after_minutes: slaResponse.late_after_minutes,
          alert_on_failure: slaResponse.alert_on_failure,
          alert_on_late: slaResponse.alert_on_late,
          notify_channels_json: JSON.stringify(slaResponse.notify_channels_json ?? {}, null, 2)
        });
      } catch {
        setSla(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load robot details.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [robotId, selectedEnv]);

  const onPublish = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!robotId || !artifactFile) {
      setError("Select an artifact file.");
      return;
    }
    if (!semverRegex.test(version)) {
      setError("Invalid SemVer format. Use x.y.z");
      return;
    }
    setPublishing(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("version", version);
      formData.append("channel", channel);
      formData.append("changelog", changelog);
      formData.append("entrypoint_path", entrypointPath);
      formData.append("entrypoint_type", entrypointType);
      formData.append("activate", publishActivate ? "true" : "false");
      formData.append("artifact", artifactFile);
      await publishRobotVersion(robotId, formData, token);
      setVersion("");
      setChangelog("");
      setArtifactFile(null);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish version.");
    } finally {
      setPublishing(false);
    }
  };

  const onActivate = async (versionId: string) => {
    if (!robotId) return;
    setError(null);
    try {
      await activateRobotVersion(robotId, versionId, token);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate version.");
    }
  };

  const onSaveEnvVar = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!robotId) return;
    if (!envKey.trim()) {
      setError("Informe a key da configuracao.");
      return;
    }
    if (!envValue) {
      setError("Informe o valor da configuracao.");
      return;
    }

    setError(null);
    try {
      await upsertRobotEnvVars(
        robotId,
        selectedEnv,
        [{ key: envKey.trim().toUpperCase(), value: envValue, is_secret: envIsSecret }],
        token
      );
      setEnvKey("");
      setEnvValue("");
      setEnvIsSecret(false);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar configuracao.");
    }
  };

  const onDeleteEnvVar = async (key: string) => {
    if (!robotId) return;
    if (!window.confirm(`Remover a key '${key}' do ambiente ${selectedEnv}?`)) return;
    setError(null);
    try {
      await deleteRobotEnvVar(robotId, selectedEnv, key, token);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover key.");
    }
  };

  const onSaveSchedule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!robotId) return;
    setError(null);
    const payload = {
      enabled: scheduleForm.enabled,
      cron_expr: scheduleForm.cron_expr,
      timezone: scheduleForm.timezone,
      window_start: scheduleForm.window_start || null,
      window_end: scheduleForm.window_end || null,
      max_concurrency: Number(scheduleForm.max_concurrency),
      timeout_seconds: Number(scheduleForm.timeout_seconds),
      retry_count: Number(scheduleForm.retry_count),
      retry_backoff_seconds: Number(scheduleForm.retry_backoff_seconds)
    };

    try {
      if (schedule) {
        await updateRobotSchedule(robotId, payload, token);
      } else {
        await createRobotSchedule(robotId, payload, token);
      }
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar agendamento.");
    }
  };

  const onDeleteSchedule = async () => {
    if (!robotId) return;
    setError(null);
    try {
      await deleteRobotSchedule(robotId, token);
      setSchedule(null);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover agendamento.");
    }
  };

  const onSaveSla = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!robotId) return;

    let notifyChannels: Record<string, unknown>;
    try {
      notifyChannels = JSON.parse(slaForm.notify_channels_json || "{}");
    } catch {
      setError("notify_channels_json invalido.");
      return;
    }

    setError(null);
    const payload = {
      expected_run_every_minutes: slaForm.expected_run_every_minutes > 0 ? Number(slaForm.expected_run_every_minutes) : null,
      expected_daily_time: slaForm.expected_daily_time || null,
      late_after_minutes: Number(slaForm.late_after_minutes),
      alert_on_failure: slaForm.alert_on_failure,
      alert_on_late: slaForm.alert_on_late,
      notify_channels_json: notifyChannels
    };

    try {
      if (sla) {
        await updateRobotSla(robotId, payload, token);
      } else {
        await createRobotSla(robotId, payload, token);
      }
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar SLA.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Robot Management</h2>
        <p className="page-subtitle">
          Robot: <strong>{robotId}</strong> | Active version: <strong>{activeVersion?.version ?? "-"}</strong>
        </p>
        <p className="helper-text">
          <Link href="/robots" style={{ color: "#8bb4ff" }}>
            Back to robots
          </Link>
        </p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            API token (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button type="button" className="btn-secondary" onClick={() => loadAll()}>
            Refresh
          </button>
        </div>
        <div className="toolbar" style={{ marginTop: 8 }}>
          <button className={activeTab === "versions" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("versions")}>Versoes</button>
          <button className={activeTab === "schedule" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("schedule")}>Agendamento</button>
          <button className={activeTab === "sla" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("sla")}>SLA</button>
          <button className={activeTab === "config" ? "btn-primary" : "btn-secondary"} onClick={() => setActiveTab("config")}>Config/Secrets</button>
        </div>
        {loading ? <p className="helper-text">Loading...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      {activeTab === "versions" ? (
        <section className="split">
          <form className="card form-grid" onSubmit={onPublish}>
            <h3 style={{ marginTop: 0 }}>Publish New Version</h3>
            <label>
              Version (SemVer)
              <input value={version} onChange={(event) => setVersion(event.target.value)} placeholder="1.2.3" required />
            </label>
            <label>
              Channel
              <select value={channel} onChange={(event) => setChannel(event.target.value as "stable" | "beta" | "hotfix")}>
                <option value="stable">stable</option>
                <option value="beta">beta</option>
                <option value="hotfix">hotfix</option>
              </select>
            </label>
            <label>
              Entrypoint type
              <select value={entrypointType} onChange={(event) => setEntrypointType(event.target.value as "PYTHON" | "EXE")}>
                <option value="PYTHON">PYTHON</option>
                <option value="EXE">EXE</option>
              </select>
            </label>
            <label>
              Entrypoint path
              <input value={entrypointPath} onChange={(event) => setEntrypointPath(event.target.value)} placeholder="main.py" required />
            </label>
            <label>
              Changelog
              <textarea value={changelog} onChange={(event) => setChangelog(event.target.value)} />
            </label>
            <label>
              Artifact (.zip or .exe)
              <input type="file" accept=".zip,.exe" onChange={(event) => setArtifactFile(event.target.files?.[0] ?? null)} required />
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input type="checkbox" checked={publishActivate} onChange={(event) => setPublishActivate(event.target.checked)} style={{ width: 18 }} />
              Ativar versao imediatamente
            </label>
            <button type="submit" className="btn-primary" disabled={publishing}>
              {publishing ? "Publishing..." : "Publish version"}
            </button>
          </form>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Version History</h3>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Channel</th>
                    <th>Type</th>
                    <th>SHA256</th>
                    <th>Commit</th>
                    <th>Branch</th>
                    <th>Build</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Created</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((item) => (
                    <tr key={item.id} style={item.id === highlightedVersionId ? { backgroundColor: "rgba(74,125,226,0.14)" } : undefined}>
                      <td>{item.version}</td>
                      <td>{item.channel}</td>
                      <td>{item.artifact_type}</td>
                      <td style={{ maxWidth: 180, overflowWrap: "anywhere" }}>{item.artifact_sha256 ?? "-"}</td>
                      <td style={{ maxWidth: 120, overflowWrap: "anywhere" }}>{item.commit_sha ?? "-"}</td>
                      <td>{item.branch ?? "-"}</td>
                      <td>
                        {item.build_url ? (
                          <a href={item.build_url} target="_blank" rel="noreferrer" style={{ color: "#8bb4ff" }}>
                            Open
                          </a>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td>{item.is_active ? "active" : "inactive"}</td>
                      <td>{item.created_source === "github_actions" ? "github_actions" : item.created_by ? item.created_by.slice(0, 8) : "user"}</td>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>
                        <button type="button" className="btn-secondary" onClick={() => onActivate(item.id)} disabled={item.is_active}>
                          Activate
                        </button>
                      </td>
                    </tr>
                  ))}
                  {versions.length === 0 ? (
                    <tr>
                      <td colSpan={11}>No versions found.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}

      {activeTab === "schedule" ? (
        <section className="card">
          <form className="form-grid" onSubmit={onSaveSchedule}>
            <h3 style={{ marginTop: 0 }}>Agendamento corporativo</h3>
            <div className="split">
              <label>
                Cron (5 campos)
                <input value={scheduleForm.cron_expr} onChange={(event) => setScheduleForm((prev) => ({ ...prev, cron_expr: event.target.value }))} required />
              </label>
              <label>
                Timezone
                <input value={scheduleForm.timezone} onChange={(event) => setScheduleForm((prev) => ({ ...prev, timezone: event.target.value }))} required />
              </label>
            </div>
            <div className="split">
              <label>
                Janela inicio (HH:MM)
                <input value={scheduleForm.window_start} onChange={(event) => setScheduleForm((prev) => ({ ...prev, window_start: event.target.value }))} placeholder="08:00" />
              </label>
              <label>
                Janela fim (HH:MM)
                <input value={scheduleForm.window_end} onChange={(event) => setScheduleForm((prev) => ({ ...prev, window_end: event.target.value }))} placeholder="18:00" />
              </label>
            </div>
            <div className="split">
              <label>
                Max concurrency
                <input type="number" min={1} value={scheduleForm.max_concurrency} onChange={(event) => setScheduleForm((prev) => ({ ...prev, max_concurrency: Number(event.target.value) }))} />
              </label>
              <label>
                Timeout (s)
                <input type="number" min={1} value={scheduleForm.timeout_seconds} onChange={(event) => setScheduleForm((prev) => ({ ...prev, timeout_seconds: Number(event.target.value) }))} />
              </label>
            </div>
            <div className="split">
              <label>
                Retry count
                <input type="number" min={0} value={scheduleForm.retry_count} onChange={(event) => setScheduleForm((prev) => ({ ...prev, retry_count: Number(event.target.value) }))} />
              </label>
              <label>
                Retry backoff (s)
                <input type="number" min={1} value={scheduleForm.retry_backoff_seconds} onChange={(event) => setScheduleForm((prev) => ({ ...prev, retry_backoff_seconds: Number(event.target.value) }))} />
              </label>
            </div>
            <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <input type="checkbox" checked={scheduleForm.enabled} onChange={(event) => setScheduleForm((prev) => ({ ...prev, enabled: event.target.checked }))} style={{ width: 18 }} />
              Schedule habilitado
            </label>
            <div className="toolbar">
              <button type="submit" className="btn-primary">
                {schedule ? "Atualizar schedule" : "Criar schedule"}
              </button>
              {schedule ? (
                <button type="button" className="btn-secondary" onClick={() => onDeleteSchedule()}>
                  Remover schedule
                </button>
              ) : null}
            </div>
          </form>
        </section>
      ) : null}

      {activeTab === "sla" ? (
        <section className="card">
          <form className="form-grid" onSubmit={onSaveSla}>
            <h3 style={{ marginTop: 0 }}>SLA / Alertas</h3>
            <div className="split">
              <label>
                Esperado a cada X minutos
                <input
                  type="number"
                  min={0}
                  value={slaForm.expected_run_every_minutes}
                  onChange={(event) => setSlaForm((prev) => ({ ...prev, expected_run_every_minutes: Number(event.target.value) }))}
                />
              </label>
              <label>
                Horario diario esperado (HH:MM)
                <input value={slaForm.expected_daily_time} onChange={(event) => setSlaForm((prev) => ({ ...prev, expected_daily_time: event.target.value }))} placeholder="09:00" />
              </label>
            </div>
            <label>
              Tolerancia de atraso (min)
              <input
                type="number"
                min={1}
                value={slaForm.late_after_minutes}
                onChange={(event) => setSlaForm((prev) => ({ ...prev, late_after_minutes: Number(event.target.value) }))}
              />
            </label>
            <div className="split">
              <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input type="checkbox" checked={slaForm.alert_on_late} onChange={(event) => setSlaForm((prev) => ({ ...prev, alert_on_late: event.target.checked }))} style={{ width: 18 }} />
                Alertar atraso
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <input type="checkbox" checked={slaForm.alert_on_failure} onChange={(event) => setSlaForm((prev) => ({ ...prev, alert_on_failure: event.target.checked }))} style={{ width: 18 }} />
                Alertar falha recorrente
              </label>
            </div>
            <label>
              notify_channels_json
              <textarea className="json-editor" value={slaForm.notify_channels_json} onChange={(event) => setSlaForm((prev) => ({ ...prev, notify_channels_json: event.target.value }))} />
            </label>
            <button type="submit" className="btn-primary">
              {sla ? "Atualizar SLA" : "Criar SLA"}
            </button>
          </form>
        </section>
      ) : null}

      {activeTab === "config" ? (
        <section className="split">
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Config/Secrets por ambiente</h3>
            <div className="toolbar">
              <label style={{ minWidth: 200 }}>
                Ambiente
                <select value={selectedEnv} onChange={(event) => setSelectedEnv(event.target.value as "PROD" | "HML" | "TEST")}>
                  <option value="PROD">PROD</option>
                  <option value="HML">HML</option>
                  <option value="TEST">TEST</option>
                </select>
              </label>
            </div>
            {requiredEnvKeys.length > 0 ? (
              <p className="helper-text">
                Keys requeridas pela versao ativa: <strong>{requiredEnvKeys.join(", ")}</strong>
              </p>
            ) : (
              <p className="helper-text">Nenhuma key requerida declarada (robot.yaml opcional).</p>
            )}
            {missingRequiredKeys.length > 0 ? (
              <p className="helper-text" style={{ color: "#ff9a9a" }}>
                Config incompleta para {selectedEnv}. Faltando: <strong>{missingRequiredKeys.join(", ")}</strong>
              </p>
            ) : null}
            <div className="table-wrap" style={{ marginTop: 12 }}>
              <table>
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Tipo</th>
                    <th>Status</th>
                    <th>Valor</th>
                    <th>Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {envVars.map((item) => (
                    <tr key={`${item.env_name}:${item.key}`}>
                      <td>{item.key}</td>
                      <td>{item.is_secret ? "secret" : "config"}</td>
                      <td>{item.is_set ? "set" : "unset"}</td>
                      <td>{item.is_secret ? "********" : (item.value ?? "-")}</td>
                      <td>
                        <button type="button" className="btn-secondary" onClick={() => onDeleteEnvVar(item.key)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                  {envVars.length === 0 ? (
                    <tr>
                      <td colSpan={5}>Nenhuma key cadastrada neste ambiente.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </div>

          <form className="card form-grid" onSubmit={onSaveEnvVar}>
            <h3 style={{ marginTop: 0 }}>Adicionar / sobrescrever key</h3>
            <label>
              Key
              <input value={envKey} onChange={(event) => setEnvKey(event.target.value.toUpperCase())} placeholder="API_BASE_URL" required />
            </label>
            <label>
              Tipo
              <select value={envIsSecret ? "secret" : "config"} onChange={(event) => setEnvIsSecret(event.target.value === "secret")}>
                <option value="config">config</option>
                <option value="secret">secret</option>
              </select>
            </label>
            <label>
              Valor
              <input
                type={envIsSecret ? "password" : "text"}
                value={envValue}
                onChange={(event) => setEnvValue(event.target.value)}
                placeholder={envIsSecret ? "Novo valor secreto" : "Valor"}
                required
              />
            </label>
            <p className="helper-text">
              Segredos nunca sao retornados em texto. Na edicao, sempre informe um novo valor para sobrescrever.
            </p>
            <button type="submit" className="btn-primary">
              Salvar key
            </button>
          </form>
        </section>
      ) : null}
    </>
  );
}
