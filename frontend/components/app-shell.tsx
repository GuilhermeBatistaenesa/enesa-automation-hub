import Link from "next/link";
import { Bot, ChartNoAxesCombined, Gauge, PanelsTopLeft, PlaySquare, Settings2, ShieldCheck } from "lucide-react";

const links = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/portal", label: "Portal", icon: PanelsTopLeft },
  { href: "/robots", label: "Robos", icon: Bot },
  { href: "/executions", label: "Execucao", icon: PlaySquare },
  { href: "/runs", label: "Historico", icon: ChartNoAxesCombined },
  { href: "/admin/operations", label: "Operacoes", icon: ShieldCheck },
  { href: "/admin/domains", label: "Admin", icon: Settings2 }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div>
          <p className="brand-kicker">Enesa Engenharia</p>
          <h1 className="brand-title">Automation Hub</h1>
        </div>
        <nav className="nav-links">
          {links.map((link) => {
            const Icon = link.icon;
            return (
              <Link key={link.href} href={link.href} className="nav-link">
                <Icon size={18} />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">Ambiente interno corporativo</div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
