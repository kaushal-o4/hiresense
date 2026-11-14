// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/PracticeHistory.jsx
//
// FILE PURPOSE:
// All practice activities in one filterable list.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /student/history with a type filter.
//
// HOW THIS FILE WORKS:
// A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with
// useState and sends changes with post/put/patch/del, then shows results with the shared UI
// components. API calls used: GET /student/history.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: PracticeHistory
//
// INPUT:
// Filter.
//
// OUTPUT:
// History list.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx, pages/shared/filterChipStyle.js
//    Used by: pages/student/ProgressHub.jsx
//
// IMPORTANT DEPENDENCIES:
//    react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Every practice activity (interviews, English, assessments) in one filterable list (GET /student/history). */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { get } from "../../apiClient";
import { Card, ErrorBox, PageHeader, Pill, Spinner, Table, fmtDateTime, useApi } from "../../components/SharedUiComponents";
import { chipClass } from "../shared/filterChipStyle";

const TYPES = [["", "All"], ["interview", "Interviews"], ["english", "English conversations"], ["assessment", "Assessments"]];
const TONE = { interview: "brand", english: "blue", pronunciation: "violet", speaking: "blue", assessment: "amber" };

export default function PracticeHistory() {
  const navigate = useNavigate();
  const [type, setType] = useState("");
  const { data, error, loading, reload } = useApi(() => get("/student/history", { type }), [type]);
  return (
    <div className="space-y-6">
      <PageHeader title="Practice history" subtitle="Every interview, English session, drill and test you've completed. Click a row to review answers." />
      <div className="flex flex-wrap gap-2">
        {TYPES.map(([v, l]) => <button key={v || "all"} onClick={() => setType(v)} aria-pressed={type === v} className={chipClass(type === v)}>{l}</button>)}
      </div>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && <Table rows={data} rowKey={(r) => `${r.type}-${r.id}`} empty="No practice yet - start with a mock interview or English drill!"
          onRowClick={(r) => navigate(r.link)} columns={[
            { label: "Date", render: (r) => fmtDateTime(r.date) },
            { label: "Type", render: (r) => <Pill tone={TONE[r.type]}>{r.type}</Pill> },
            { label: "Activity", render: (r) => <span className="text-sm">{r.title}</span> },
            { label: "Score", render: (r) => r.pending ? <Pill tone="amber">pending</Pill> : r.score ?? "—" },
          ]} />}
      </Card>
    </div>
  );
}
