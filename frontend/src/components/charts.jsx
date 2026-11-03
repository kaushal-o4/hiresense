/*
 * Recharts wrappers (bar, multi-bar, progress line, timeline and skill radar) used by the dashboards,
 * progress pages and reports of all four portals.
 */

import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar,
  RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { EmptyState } from "./ui";

// Accent first, then hues that stay distinguishable from each other and from status colours.
export const COLORS = ["#818cf8", "#2dd4bf", "#fbbf24", "#f472b6", "#a78bfa", "#94a3b8"];
const AXIS = { fontSize: 11, fill: "#8b96b6" };
const GRID = "#1f2842";
const TOOLTIP = {
  contentStyle: { borderRadius: 10, border: "1px solid #2f3a5c", background: "rgba(14,20,38,0.95)", color: "#dfe3f0", boxShadow: "0 16px 32px -8px rgb(0 0 0 / 0.6)", fontSize: 12, padding: "8px 10px" },
  itemStyle: { color: "#dfe3f0" },
  labelStyle: { color: "#ffffff", fontWeight: 600, marginBottom: 2 },
  cursor: { fill: "rgb(129 140 248 / 0.08)", stroke: "#2f3a5c" },
};
const LEGEND = { wrapperStyle: { fontSize: 12, color: "#a6b0cb" }, iconType: "circle", iconSize: 8 };

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
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="date" tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis domain={[0, 100]} tick={AXIS} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP} />
        <Legend {...LEGEND} />
        {metrics.map((m, i) => (
          <Line key={m} type="monotone" dataKey={m} name={METRIC_LABELS[m] || m} stroke={COLORS[i % COLORS.length]}
            strokeWidth={2} connectNulls dot={{ r: 2.5, strokeWidth: 0, fill: COLORS[i % COLORS.length] }} activeDot={{ r: 4 }} />
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
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey={nameKey} tick={AXIS} tickLine={false} axisLine={false} interval={0} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} domain={max ? [0, max] : undefined} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MultiBar({ data, keys, nameKey, height = 260, max }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey={nameKey} tick={AXIS} tickLine={false} axisLine={false} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} domain={max ? [0, max] : undefined} />
        <Tooltip {...TOOLTIP} />
        <Legend {...LEGEND} />
        {keys.map((k, i) => <Bar key={k.key} dataKey={k.key} name={k.label} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} maxBarSize={28} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SkillRadar({ data, height = 260, max = 10 }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={data} outerRadius="70%">
        <PolarGrid stroke={GRID} />
        <PolarAngleAxis dataKey="label" tick={AXIS} tickLine={false} axisLine={false} />
        <PolarRadiusAxis domain={[0, max]} tick={{ ...AXIS, fontSize: 10 }} tickLine={false} axisLine={false} />
        <Radar dataKey="value" stroke={COLORS[0]} fill={COLORS[0]} fillOpacity={0.15} strokeWidth={2} />
        <Tooltip {...TOOLTIP} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

export function TimelineChart({ data, keys, height = 260 }) {
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="date" tick={{ ...AXIS, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(d) => d.slice(5)} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Legend {...LEGEND} />
        {keys.map((k, i) => <Line key={k.key} dataKey={k.key} name={k.label} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}
