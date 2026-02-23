"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { createDomain, deleteDomain, fetchDomains, updateDomain } from "@/lib/api";
import { Domain } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export default function AdminDomainsPage() {
  const [token, setToken] = useState(defaultToken);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editSlug, setEditSlug] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const loadDomains = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetchDomains(token);
      setDomains(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dominios.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDomains().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    try {
      await createDomain({ name, slug, description: description || null }, token);
      setName("");
      setSlug("");
      setDescription("");
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar dominio.");
    }
  };

  const onStartEdit = (domain: Domain) => {
    setEditingId(domain.id);
    setEditName(domain.name);
    setEditSlug(domain.slug);
    setEditDescription(domain.description ?? "");
  };

  const onSaveEdit = async () => {
    if (!editingId) return;
    setError(null);
    try {
      await updateDomain(editingId, { name: editName, slug: editSlug, description: editDescription || null }, token);
      setEditingId(null);
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao atualizar dominio.");
    }
  };

  const onDelete = async (domainId: string) => {
    setError(null);
    try {
      await deleteDomain(domainId, token);
      await loadDomains();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao remover dominio.");
    }
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Admin - Dominios</h2>
        <p className="page-subtitle">Crie areas do portal de autoatendimento como DP/RH, Engenharia e Suprimentos.</p>
        <p className="helper-text">
          <Link href="/admin/services" style={{ color: "#8bb4ff" }}>
            Ir para admin de servicos
          </Link>
        </p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" onClick={() => loadDomains()}>
            Recarregar
          </button>
        </div>
        {loading ? <p className="helper-text">Carregando...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="split">
        <form className="card form-grid" onSubmit={onCreate}>
          <h3 style={{ marginTop: 0 }}>Novo dominio</h3>
          <label>
            Nome
            <input value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
          <label>
            Slug
            <input value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="dp-rh" required />
          </label>
          <label>
            Descricao
            <textarea value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <button className="btn-primary" type="submit">
            Criar dominio
          </button>
        </form>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Dominios cadastrados</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Slug</th>
                  <th>Criado</th>
                  <th>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {domains.map((domain) => (
                  <tr key={domain.id}>
                    <td>{domain.name}</td>
                    <td>{domain.slug}</td>
                    <td>{new Date(domain.created_at).toLocaleString()}</td>
                    <td>
                      <div className="toolbar" style={{ margin: 0 }}>
                        <button type="button" className="btn-secondary" onClick={() => onStartEdit(domain)}>
                          Editar
                        </button>
                        <button type="button" className="btn-secondary" onClick={() => onDelete(domain.id)}>
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {domains.length === 0 ? (
                  <tr>
                    <td colSpan={4}>Nenhum dominio cadastrado.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {editingId ? (
        <section className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Editar dominio</h3>
          <div className="split">
            <label>
              Nome
              <input value={editName} onChange={(event) => setEditName(event.target.value)} />
            </label>
            <label>
              Slug
              <input value={editSlug} onChange={(event) => setEditSlug(event.target.value)} />
            </label>
          </div>
          <label style={{ marginTop: 10 }}>
            Descricao
            <textarea value={editDescription} onChange={(event) => setEditDescription(event.target.value)} />
          </label>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button className="btn-primary" type="button" onClick={() => onSaveEdit()}>
              Salvar alteracoes
            </button>
            <button className="btn-secondary" type="button" onClick={() => setEditingId(null)}>
              Cancelar
            </button>
          </div>
        </section>
      ) : null}
    </>
  );
}
