/* Every practice activity (interviews, English, assessments) in one filterable list (GET /student/history). */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { get } from "../../api";
import { Card, ErrorBox, PageHeader, Pill, Spinner, Table, fmtDateTime, useApi } from "../../components/ui";
import { chipClass } from "../shared/chips";

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
