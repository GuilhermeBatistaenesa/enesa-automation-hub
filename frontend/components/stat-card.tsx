type StatCardProps = {
  label: string;
  value: string | number;
  subtitle?: string;
};

export function StatCard({ label, value, subtitle }: StatCardProps) {
  return (
    <article className="card">
      <p className="card-label">{label}</p>
      <h3 className="card-value">{value}</h3>
      {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
    </article>
  );
}
