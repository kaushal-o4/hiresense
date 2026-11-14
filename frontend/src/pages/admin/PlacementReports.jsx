// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/admin/PlacementReports.jsx
//
// FILE PURPOSE:
// Placement report table with CSV export.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /admin/reports/placements.
// 2. Downloads CSV with ?format=csv.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /admin/reports/placements.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: Reports
//
// INPUT:
// Report data.
//
// OUTPUT:
// Table and CSV file.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Placement report table and CSV export (/admin/reports/placements). */

import { Download } from "lucide-react";
import { download, get } from "../../apiClient";
import { Button, Card, ErrorBox, PageHeader, Spinner, StatCard, StatusPill, Table, fmtDateTime, useApi, useToast } from "../../components/SharedUiComponents";

export default function Reports() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => get("/admin/reports/placements"));
  return (
    <div className="space-y-6">
      <PageHeader title="Performance & placement report" subtitle={data ? `Generated ${fmtDateTime(data.generated_at)}` : ""}
        actions={<>
          <Button variant="secondary" onClick={reload}>Regenerate</Button>
          <Button onClick={() => download("/admin/reports/placements?format=csv", "hiresense_placement_report.csv").catch((e) => toast(e.message, "error"))}><Download size={16} /> Download CSV</Button>
        </>} />
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard label="Students" value={data.students} />
            <StatCard label="Placed" value={data.placed} tone="green" />
            <StatCard label="Placement rate" value={`${data.placement_rate}%`} tone="amber" />
          </div>
          <Card bodyClass="">
            <Table rows={data.rows} rowKey={(r) => r.student_id} empty="No students registered yet" columns={[
              { label: "Student", render: (r) => <div><p className="font-medium">{r.name}</p><p className="text-xs text-slate-500">{r.email}</p></div> },
              { label: "Branch", render: (r) => r.branch || "—" }, { label: "CGPA", render: (r) => r.cgpa === "" ? "—" : r.cgpa },
              { label: "Interviews", render: (r) => `${r.interviews} · ${r.interview_avg === "" ? "—" : r.interview_avg}` },
              { label: "English min", key: "english_minutes" }, { label: "Assess. avg", render: (r) => r.assessment_avg === "" ? "—" : r.assessment_avg },
              { label: "Points", key: "points" }, { label: "Applications", key: "applications" },
              { label: "Selected at", render: (r) => r.selected || "—" }, { label: "Trend", render: (r) => <StatusPill status={r.trend} /> }]} />
          </Card>
        </>
      )}
    </div>
  );
}
