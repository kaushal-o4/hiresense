import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar,
  RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { EmptyState } from "./ui";

export const COLORS = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const METRIC_LABELS = {
  interview_score: "Interview", english_score: "English", assessment_score: "Assessment",
  technical_score: "Technical", hr_score: "HR", behavioral_score: "Behavioral", communication_score: "Communication",
};

/** Line chart of progress records. `series` = [{metric, value, date}] */
export function ProgressChart({ series, metrics = ["interview_score", "english_score", "assessment_score"], height = 260 }) {
  const rows = (series || []).filter((s) => metrics.includes(s.metric));
  if (!rows.length) return <EmptyState title="No scores yet" message="Complete an interview, English session or assessment to see your progress." />;
  const data = rows.map((r, i) => ({ idx: i + 1, date: new Date(r.date).toLocaleDateString(undefined, { day: "numeric", month: "short" }), [r.metric]: r.value }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {metrics.map((m, i) => (
          <Line key={m} type="monotone" dataKey={m} name={METRIC_LABELS[m] || m} stroke={COLORS[i % COLORS.length]}
            strokeWidth={2} connectNulls dot={{ r: 3 }} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SimpleBar({ data, dataKey, nameKey, height = 240, color = COLORS[0], max }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey={nameKey} tick={{ fontSize: 11 }} interval={0} />
        <YAxis tick={{ fontSize: 11 }} domain={max ? [0, max] : undefined} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MultiBar({ data, keys, nameKey, height = 260, max }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey={nameKey} tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} domain={max ? [0, max] : undefined} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => <Bar key={k.key} dataKey={k.key} name={k.label} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SkillRadar({ data, height = 260, max = 10 }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="70%">
        <PolarGrid />
        <PolarAngleAxis dataKey="label" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis domain={[0, max]} tick={{ fontSize: 10 }} />
        <Radar dataKey="value" stroke={COLORS[0]} fill={COLORS[0]} fillOpacity={0.3} />
        <Tooltip />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function TimelineChart({ data, keys, height = 260 }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => <Line key={k.key} dataKey={k.key} name={k.label} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}
