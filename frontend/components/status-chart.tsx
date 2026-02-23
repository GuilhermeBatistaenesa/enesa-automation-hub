"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

type StatusChartData = {
  name: string;
  value: number;
};

const COLORS = ["#4a7de2", "#f6c350", "#30d58f", "#ef6363"];

export function StatusChart({ data }: { data: StatusChartData[] }) {
  return (
    <div className="chart-card">
      <h3>Distribuição de status</h3>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" outerRadius={94}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
