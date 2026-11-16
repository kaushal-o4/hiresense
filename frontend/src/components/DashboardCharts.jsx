// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/DashboardCharts.jsx
//
// FILE PURPOSE:
// Ready-made chart components (built on Recharts) used by the dashboards, progress pages and reports.
//
// WHAT THIS FILE DOES:
// 1. ProgressChart: line chart of a student's scores over time.
// 2. SimpleBar and MultiBar: bar charts.
// 3. SkillRadar: radar (spider) chart of skill scores.
// 4. TimelineChart: multi-line chart of scores by session.
// 5. Shows an empty state when there is no data.
//
// HOW THIS FILE WORKS:
// Each function receives data arrays and wraps Recharts components with the app's colours, axis and
// tooltip styles.
//
// IMPORTANT FUNCTIONS:
//    - ProgressChart()
//        Line chart of progress records (interview, English, assessment scores) by date.
//    - SimpleBar()
//        Single-series bar chart.
//    - MultiBar()
//        Bar chart with several series per item.
//    - SkillRadar()
//        Radar chart of scores 0-10.
//    - TimelineChart()
//        Lines for several keys across sessions.
//
// IMPORTANT VARIABLES / STATE:
//    - COLORS
//        Colour list used for chart series.
//
// INPUT:
// Data arrays and options (keys, height, max) from the calling page.
//
// OUTPUT:
// SVG charts in the page.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/SharedUiComponents.jsx
//    Used by: components/EnglishProgress.jsx, pages/admin/AdminDashboard.jsx,
//    pages/admin/AdminMonitoring.jsx, pages/mentor/MentorDashboard.jsx,
//    pages/recruiter/RecruiterDashboard.jsx, pages/student/EnglishSession.jsx,
//    pages/student/PerformanceReport.jsx, pages/student/ProgressOverview.jsx,
//    pages/student/StudentDashboard.jsx
//
// IMPORTANT DEPENDENCIES:
//    recharts
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Recharts wrappers (bar, multi-bar, progress line, timeline and skill radar) used by the dashboards,
 * progress pages and reports of all four portals.
 */

import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar,
  RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { EmptyState } from "./SharedUiComponents";
import { useTheme } from "./ThemeContext";

// HireSense categorical palette: brand blue first, then hues distinct from each other and from status colours.
const LIGHT = { colors: ["#315EF7", "#14A3A0", "#E9A23B", "#7C8BA1", "#DC5353", "#4BA3E3"], axis: "#697586", grid: "#E5E9F0",
  tipBg: "#FFFFFF", tipBorder: "#E5E9F0", tipText: "#172333", cursor: "rgb(49 94 247 / 0.06)" };
const DARK = { colors: ["#4778FF", "#2CC4BE", "#F0B95A", "#A0ADC0", "#F07878", "#6CB8F0"], axis: "#8B97AA", grid: "#263142",
  tipBg: "#172333", tipBorder: "#2F3D52", tipText: "#E6EAF1", cursor: "rgb(71 120 255 / 0.10)" };

// Re-read on theme change (ThemeContext sets html[data-theme]).
function useChartTheme() {
  const { resolved } = useTheme();
  const t = resolved === "dark" ? DARK : LIGHT;
  return {
    COLORS: t.colors,
    AXIS: { fontSize: 11, fill: t.axis },
    GRID: t.grid,
    TOOLTIP: {
      contentStyle: { borderRadius: 10, border: `1px solid ${t.tipBorder}`, background: t.tipBg, color: t.tipText,
        boxShadow: "0 12px 28px -8px rgb(16 21 29 / 0.25)", fontSize: 12, padding: "8px 10px" },
      itemStyle: { color: t.tipText },
      labelStyle: { color: t.tipText, fontWeight: 600, marginBottom: 2 },
      cursor: { fill: t.cursor, stroke: t.grid },
    },
    LEGEND: { wrapperStyle: { fontSize: 12, color: t.axis }, iconType: "circle", iconSize: 8 },
  };
}

/** Exported for pages that colour a single series by hand. */
export const COLORS = LIGHT.colors;

const METRIC_LABELS = {
  interview_score: "Interview", english_score: "English", assessment_score: "Assessment",
  technical_score: "Technical", hr_score: "HR", behavioral_score: "Behavioral", communication_score: "Communication",
};

/** Line chart of progress records. `series` = [{metric, value, date}] */
export function ProgressChart({ series, metrics = ["interview_score", "english_score", "assessment_score"], height = 260 }) {
  const { COLORS, AXIS, GRID, TOOLTIP, LEGEND } = useChartTheme();
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

/** `tone` = index into the theme palette (0 = brand blue, 1 = teal, 2 = amber ...). */
export function SimpleBar({ data, dataKey, nameKey, height = 240, tone = 0, max }) {
  const { COLORS, AXIS, GRID, TOOLTIP } = useChartTheme();
  const fill = COLORS[tone % COLORS.length];
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey={nameKey} tick={AXIS} tickLine={false} axisLine={false} interval={0} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} domain={max ? [0, max] : undefined} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Bar dataKey={dataKey} fill={fill} radius={[4, 4, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function MultiBar({ data, keys, nameKey, height = 260, max }) {
  const { COLORS, AXIS, GRID, TOOLTIP, LEGEND } = useChartTheme();
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
  const { COLORS, AXIS, GRID, TOOLTIP } = useChartTheme();
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
  const { COLORS, AXIS, GRID, TOOLTIP, LEGEND } = useChartTheme();
  if (!data?.length) return <EmptyState title="No data yet" />;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="date" tick={{ ...AXIS, fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(d) => d.slice(5)} minTickGap={24} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
        <Tooltip {...TOOLTIP} />
        <Legend {...LEGEND} />
        {keys.map((k, i) => <Line key={k.key} type="monotone" dataKey={k.key} name={k.label} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}
