"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";

import { activateRobotVersion, fetchRobotVersions, publishRobotVersion } from "@/lib/api";
import { RobotVersion } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const semverRegex = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/;

export default function RobotDetailsPage() {
  const params = useParams<{ robotId: string }>();
  const searchParams = useSearchParams();
  const robotId = params.robotId;
  const highlightedVersionId = searchParams.get("versionId");

  const [token, setToken] = useState(defaultToken);
  const [versions, setVersions] = useState<RobotVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);

  const [version, setVersion] = useState("");
  const [channel, setChannel] = useState<"stable" | "beta" | "hotfix">("stable");
  const [changelog, setChangelog] = useState("");
  const [entrypointPath, setEntrypointPath] = useState("main.py");
  const [entrypointType, setEntrypointType] = useState<"PYTHON" | "EXE">("PYTHON");
  const [artifactFile, setArtifactFile] = useState<File | null>(null);

  const activeVersion = useMemo(() => versions.find((item) => item.is_active), [versions]);

  const loadVersions = async () => {
    if (!robotId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await fetchRobotVersions(robotId, token);
      setVersions(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load versions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVersions().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [robotId]);

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
      formData.append("artifact", artifactFile);
      await publishRobotVersion(robotId, formData, token);
      setVersion("");
      setChangelog("");
      setArtifactFile(null);
      await loadVersions();
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
      await loadVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to activate version.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Robot Versions Registry</h2>
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
          <button type="button" className="btn-secondary" onClick={() => loadVersions()}>
            Refresh versions
          </button>
        </div>
        {loading ? <p className="helper-text">Loading...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

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
            <input
              type="file"
              accept=".zip,.exe"
              onChange={(event) => setArtifactFile(event.target.files?.[0] ?? null)}
              required
            />
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
                  <th>Status</th>
                  <th>Author</th>
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
                    <td>{item.is_active ? "active" : "inactive"}</td>
                    <td>{item.created_by ? item.created_by.slice(0, 8) : "-"}</td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => onActivate(item.id)}
                        disabled={item.is_active}
                      >
                        Activate
                      </button>
                    </td>
                  </tr>
                ))}
                {versions.length === 0 ? (
                  <tr>
                    <td colSpan={8}>No versions found.</td>
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
