"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type PerformanceChartPoint = {
  label: string;
  duration: number;
};

export function PerformanceChart({ data }: { data: PerformanceChartPoint[] }) {
  return (
    <div className="chart-card">
      <h3>Duração das últimas execuções</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a3852" />
          <XAxis dataKey="label" stroke="#9fb4d9" />
          <YAxis stroke="#9fb4d9" />
          <Tooltip />
          <Line type="monotone" dataKey="duration" stroke="#50e3c2" strokeWidth={2.5} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
