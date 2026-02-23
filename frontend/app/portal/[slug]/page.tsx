"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { fetchDomainServices, fetchDomains } from "@/lib/api";
import { Domain, Service } from "@/lib/types";

const defaultToken = process.env.NEXT_PUBLIC_API_TOKEN ?? "";

export default function PortalDomainServicesPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;

  const [token, setToken] = useState(defaultToken);
  const [services, setServices] = useState<Service[]>([]);
  const [domain, setDomain] = useState<Domain | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadContent = async () => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    try {
      const [domains, domainServices] = await Promise.all([fetchDomains(token), fetchDomainServices(slug, token)]);
      setDomain(domains.find((item) => item.slug === slug) ?? null);
      setServices(domainServices);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar servicos.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadContent().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  return (
    <>
      <header className="page-header">
        <h2 className="page-title">{domain?.name ?? "Portal de Servicos"}</h2>
        <p className="page-subtitle">{domain?.description ?? "Escolha uma acao e execute com parametros guiados."}</p>
        <p className="helper-text">
          <Link href="/portal" style={{ color: "#8bb4ff" }}>
            Voltar para dominios
          </Link>
        </p>
      </header>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="toolbar">
          <label style={{ minWidth: 340 }}>
            Token API (Bearer)
            <input value={token} onChange={(event) => setToken(event.target.value)} />
          </label>
          <button className="btn-secondary" onClick={() => loadContent()}>
            Recarregar
          </button>
        </div>
        {loading ? <p className="helper-text">Carregando servicos...</p> : null}
        {error ? <p className="helper-text" style={{ color: "#ff9a9a" }}>{error}</p> : null}
      </section>

      <section className="card-grid">
        {services.map((service) => (
          <Link key={service.id} href={`/portal/${slug}/${service.id}`} className="service-card">
            <div>
              <div className="toolbar" style={{ marginBottom: 8 }}>
                <span className="status-pill success">{service.enabled ? "Disponivel" : "Indisponivel"}</span>
              </div>
              <h3 style={{ margin: "0 0 6px" }}>{service.title}</h3>
              <p className="helper-text">{service.description || "Sem descricao."}</p>
            </div>
            <p className="helper-text">Abrir formulario</p>
          </Link>
        ))}
      </section>

      {!loading && services.length === 0 ? (
        <section className="card">
          <p className="helper-text">Nenhum servico habilitado para este dominio.</p>
        </section>
      ) : null}
    </>
  );
}
