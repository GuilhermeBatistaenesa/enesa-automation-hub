"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { createRobot, fetchRobots } from "@/lib/api";
import { Robot } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export default function RobotsPage() {
  const [token, setToken] = useState(defaultToken);
  const [robots, setRobots] = useState<Robot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [version, setVersion] = useState("1.0.0");
  const [entrypointType, setEntrypointType] = useState<"PYTHON" | "EXE">("PYTHON");
  const [entrypointPath, setEntrypointPath] = useState("");
  const [argumentsRaw, setArgumentsRaw] = useState("");
  const [envRaw, setEnvRaw] = useState("");
  const [workingDirectory, setWorkingDirectory] = useState("");
  const [checksum, setChecksum] = useState("");
  const [tagsRaw, setTagsRaw] = useState("");

  const parsedArguments = useMemo(
    () =>
      argumentsRaw
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [argumentsRaw]
  );

  const parsedEnv = useMemo(() => {
    const output: Record<string, string> = {};
    envRaw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .forEach((line) => {
        const [key, ...rest] = line.split("=");
        if (key && rest.length > 0) {
          output[key.trim()] = rest.join("=").trim();
        }
      });
    return output;
  }, [envRaw]);

  const parsedTags = useMemo(
    () =>
      tagsRaw
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    [tagsRaw]
  );

  const loadRobots = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchRobots(token);
      setRobots(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar robôs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRobots().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    try {
      await createRobot(
        {
          name,
          description,
          tags: parsedTags,
          initial_version: {
            version,
            channel: "stable",
            artifact_type: entrypointType === "EXE" ? "EXE" : "ZIP",
            artifact_path: null,
            artifact_sha256: checksum || null,
            changelog: "Initial release",
            entrypoint_type: entrypointType,
            entrypoint_path: entrypointPath,
            arguments: parsedArguments,
            env_vars: parsedEnv,
            working_directory: workingDirectory || null,
            checksum: checksum || null
          }
        },
        token
      );
      setName("");
      setDescription("");
      setEntrypointPath("");
      setArgumentsRaw("");
      setEnvRaw("");
      setWorkingDirectory("");
      setChecksum("");
      setTagsRaw("");
      await loadRobots();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao registrar robô.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Cadastro de Robôs</h2>
        <p className="page-subtitle">Registro versionado de automações Python/EXE com rastreabilidade de configuração.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} placeholder="JWT para autenticação" />
          </label>
          <button type="button" className="btn-secondary" onClick={() => loadRobots()}>
            Recarregar
          </button>
        </div>
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="split">
        <form className="card form-grid" onSubmit={onSubmit}>
          <h3 style={{ marginTop: 0 }}>Registrar novo robô</h3>
          <label>
            Nome
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            Descrição
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>
            Tags de escopo (separadas por vírgula)
            <input value={tagsRaw} onChange={(event) => setTagsRaw(event.target.value)} placeholder="financeiro,critico,sap" />
          </label>
          <label>
            Versão inicial
            <input value={version} onChange={(event) => setVersion(event.target.value)} required />
          </label>
          <label>
            Tipo de entrypoint
            <select value={entrypointType} onChange={(event) => setEntrypointType(event.target.value as "PYTHON" | "EXE")}>
              <option value="PYTHON">PYTHON</option>
              <option value="EXE">EXE</option>
            </select>
          </label>
          <label>
            Caminho do entrypoint
            <input value={entrypointPath} onChange={(event) => setEntrypointPath(event.target.value)} placeholder="./robots/financeiro/main.py" required />
          </label>
          <label>
            Argumentos padrão (separados por vírgula)
            <input value={argumentsRaw} onChange={(event) => setArgumentsRaw(event.target.value)} placeholder="--ambiente=prod,--tenant=enesa" />
          </label>
          <label>
            Variáveis de ambiente (KEY=VALUE por linha)
            <textarea value={envRaw} onChange={(event) => setEnvRaw(event.target.value)} />
          </label>
          <label>
            Diretório de trabalho
            <input value={workingDirectory} onChange={(event) => setWorkingDirectory(event.target.value)} placeholder="C:\\Robots\\Financeiro" />
          </label>
          <label>
            Checksum (opcional)
            <input value={checksum} onChange={(event) => setChecksum(event.target.value)} />
          </label>
          <button className="btn-primary" type="submit">
            Registrar robô
          </button>
        </form>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Robôs cadastrados</h3>
          {loading ? <p className="helper-text">Carregando...</p> : null}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Tags</th>
                  <th>Versões</th>
                  <th>Atualizado em</th>
                </tr>
              </thead>
              <tbody>
                {robots.map((robot) => (
                  <tr key={robot.id}>
                    <td>
                      <Link href={`/robots/${robot.id}`} style={{ color: "#8bb4ff" }}>
                        {robot.name}
                      </Link>
                    </td>
                    <td>{robot.tags.join(", ") || "-"}</td>
                    <td>{robot.versions.length}</td>
                    <td>{new Date(robot.updated_at).toLocaleString()}</td>
                  </tr>
                ))}
                {robots.length === 0 ? (
                  <tr>
                    <td colSpan={4}>Nenhum robô encontrado.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </>
  );
}
