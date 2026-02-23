"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { createService, deleteService, fetchDomains, fetchRobots, fetchServices, updateService } from "@/lib/api";
import { Domain, Robot, Service } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";
const SAMPLE_SCHEMA = `{
  "fields": [
    {
      "key": "periodo",
      "label": "Periodo (YYYY-MM)",
      "type": "text",
      "required": true,
      "helpText": "Exemplo: 2026-02",
      "validation": {
        "regex": "^\\\\d{4}-\\\\d{2}$"
      }
    },
    {
      "key": "incluir_inativos",
      "label": "Incluir colaboradores inativos",
      "type": "checkbox",
      "default": false
    }
  ]
}`;

const SAMPLE_TEMPLATE = `{
  "defaults": {
    "incluir_inativos": false
  },
  "mapping": {
    "runtime_arguments": [
      "--periodo={periodo}",
      "--inativos={incluir_inativos}"
    ],
    "runtime_env": {
      "SERVICE_ORIGIN": "portal"
    }
  }
}`;

export default function AdminServicesPage() {
  const [token, setToken] = useState(defaultToken);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [robots, setRobots] = useState<Robot[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingServiceId, setEditingServiceId] = useState<string | null>(null);
  const [domainId, setDomainId] = useState("");
  const [robotId, setRobotId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [defaultVersionId, setDefaultVersionId] = useState("");
  const [schemaRaw, setSchemaRaw] = useState(SAMPLE_SCHEMA);
  const [templateRaw, setTemplateRaw] = useState(SAMPLE_TEMPLATE);

  const selectedRobot = useMemo(() => robots.find((robot) => robot.id === robotId), [robots, robotId]);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedDomains, loadedRobots, loadedServices] = await Promise.all([
        fetchDomains(token),
        fetchRobots(token),
        fetchServices(token)
      ]);
      setDomains(loadedDomains);
      setRobots(loadedRobots.items);
      setServices(loadedServices);

      if (!domainId && loadedDomains[0]) setDomainId(loadedDomains[0].id);
      if (!robotId && loadedRobots.items[0]) {
        setRobotId(loadedRobots.items[0].id);
        const active = loadedRobots.items[0].versions.find((version) => version.is_active);
        setDefaultVersionId(active?.id ?? loadedRobots.items[0].versions[0]?.id ?? "");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados de servico.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedRobot) return;
    const active = selectedRobot.versions.find((version) => version.is_active);
    setDefaultVersionId(active?.id ?? selectedRobot.versions[0]?.id ?? "");
  }, [selectedRobot]);

  const resetForm = () => {
    setEditingServiceId(null);
    setTitle("");
    setDescription("");
    setIcon("");
    setEnabled(true);
    setSchemaRaw(SAMPLE_SCHEMA);
    setTemplateRaw(SAMPLE_TEMPLATE);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);

    let parsedSchema: unknown;
    let parsedTemplate: unknown;
    try {
      parsedSchema = JSON.parse(schemaRaw);
      parsedTemplate = JSON.parse(templateRaw);
    } catch {
      setError("JSON invalido em schema/template.");
      return;
    }

    const payload = {
      domain_id: domainId,
      robot_id: robotId,
      title,
      description: description || null,
      icon: icon || null,
      enabled,
      default_version_id: defaultVersionId || null,
      form_schema_json: parsedSchema,
      run_template_json: parsedTemplate
    };

    try {
      if (editingServiceId) {
        await updateService(editingServiceId, payload, token);
      } else {
        await createService(payload, token);
      }
      resetForm();
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar servico.");
    }
  };

  const onEdit = (service: Service) => {
    setEditingServiceId(service.id);
    setDomainId(service.domain_id);
    setRobotId(service.robot_id);
    setTitle(service.title);
    setDescription(service.description ?? "");
    setIcon(service.icon ?? "");
    setEnabled(service.enabled);
    setDefaultVersionId(service.default_version_id ?? "");
    setSchemaRaw(JSON.stringify(service.form_schema_json, null, 2));
    setTemplateRaw(JSON.stringify(service.run_template_json, null, 2));
  };

  const onDelete = async (serviceId: string) => {
    setError(null);
    try {
      await deleteService(serviceId, token);
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover servico.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Admin - Servicos</h2>
        <p className="page-subtitle">Transforme robos em servicos reutilizaveis com formulario e template de execucao.</p>
        <p className="helper-text">
          <Link href="/admin/domains" style={{ color: "#8bb4ff" }}>
            Ir para admin de dominios
          </Link>
        </p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" onClick={() => loadAll()}>
            Recarregar
          </button>
        </div>
        {loading ? <p className="helper-text">Carregando...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="split">
        <form className="card form-grid" onSubmit={onSubmit}>
          <h3 style={{ marginTop: 0 }}>{editingServiceId ? "Editar servico" : "Novo servico"}</h3>
          <label>
            Dominio
            <select value={domainId} onChange={(event) => setDomainId(event.target.value)} required>
              {domains.map((domain) => (
                <option key={domain.id} value={domain.id}>
                  {domain.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Robo vinculado
            <select value={robotId} onChange={(event) => setRobotId(event.target.value)} required>
              {robots.map((robot) => (
                <option key={robot.id} value={robot.id}>
                  {robot.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Versao default
            <select value={defaultVersionId} onChange={(event) => setDefaultVersionId(event.target.value)}>
              <option value="">Sem versao fixa (usar ativa)</option>
              {(selectedRobot?.versions ?? []).map((version) => (
                <option key={version.id} value={version.id}>
                  {version.version} ({version.channel}) {version.is_active ? "[active]" : ""}
                </option>
              ))}
            </select>
          </label>
          <label>
            Titulo
            <input value={title} onChange={(event) => setTitle(event.target.value)} required />
          </label>
          <label>
            Descricao
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>
            Icone
            <input value={icon} onChange={(event) => setIcon(event.target.value)} placeholder="file-text" />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} style={{ width: 18 }} />
            Servico habilitado
          </label>
          <label>
            form_schema_json
            <textarea className="json-editor" value={schemaRaw} onChange={(event) => setSchemaRaw(event.target.value)} />
          </label>
          <label>
            run_template_json
            <textarea className="json-editor" value={templateRaw} onChange={(event) => setTemplateRaw(event.target.value)} />
          </label>
          <div className="toolbar">
            <button className="btn-primary" type="submit">
              {editingServiceId ? "Salvar servico" : "Criar servico"}
            </button>
            {editingServiceId ? (
              <button type="button" className="btn-secondary" onClick={() => resetForm()}>
                Cancelar edicao
              </button>
            ) : null}
          </div>
        </form>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Servicos cadastrados</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Titulo</th>
                  <th>Dominio</th>
                  <th>Robo</th>
                  <th>Status</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {services.map((service) => (
                  <tr key={service.id}>
                    <td>{service.title}</td>
                    <td>{domains.find((domain) => domain.id === service.domain_id)?.name ?? service.domain_id.slice(0, 8)}</td>
                    <td>{robots.find((robot) => robot.id === service.robot_id)?.name ?? service.robot_id.slice(0, 8)}</td>
                    <td>{service.enabled ? "enabled" : "disabled"}</td>
                    <td>
                      <div className="toolbar" style={{ margin: 0 }}>
                        <button type="button" className="btn-secondary" onClick={() => onEdit(service)}>
                          Editar
                        </button>
                        <button type="button" className="btn-secondary" onClick={() => onDelete(service.id)}>
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {services.length === 0 ? (
                  <tr>
                    <td colSpan={5}>Nenhum servico cadastrado.</td>
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
