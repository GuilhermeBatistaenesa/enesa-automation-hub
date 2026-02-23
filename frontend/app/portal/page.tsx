"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { fetchDomains } from "@/lib/api";
import { Domain } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export default function PortalDomainsPage() {
  const [token, setToken] = useState(defaultToken);
  const [domains, setDomains] = useState<Domain[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const onApplyToken = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadDomains();
  };

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">Portal de Autoatendimento</h2>
        <p className="page-subtitle">Escolha um dominio e execute servicos sem precisar conhecer detalhes tecnicos do robo.</p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <form className="toolbar" onSubmit={onApplyToken}>
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" type="submit">
            Atualizar
          </button>
        </form>
        {loading ? <p className="helper-text">Carregando dominios...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="card-grid">
        {domains.map((domain) => (
          <Link key={domain.id} href={`/portal/${domain.slug}`} className="service-card">
            <div>
              <p className="card-label">Dominio</p>
              <h3 style={{ margin: "4px 0 6px" }}>{domain.name}</h3>
              <p className="helper-text">{domain.description || "Sem descricao."}</p>
            </div>
            <p className="helper-text">Acessar servicos</p>
          </Link>
        ))}
      </section>

      {!loading && domains.length === 0 ? (
        <section className="card">
          <p className="helper-text">Nenhum dominio cadastrado. Use Admin para criar dominios e servicos.</p>
        </section>
      ) : null}
    </>
  );
}
