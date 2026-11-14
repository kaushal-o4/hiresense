// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/admin/AuditLogs.jsx
//
// FILE PURPOSE:
// Read-only audit log of admin and security actions.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /admin/audit-logs with an action filter.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /admin/audit-logs.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: AuditLogs
//
// INPUT:
// Filter.
//
// OUTPUT:
// Audit table.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Read-only audit log of admin and security actions, filterable by action. */

import { useState } from "react";
import { Search } from "lucide-react";
import { get } from "../../apiClient";
import { Button, Card, ErrorBox, PageHeader, Pagination, Spinner, Table, fmtDateTime, useApi } from "../../components/SharedUiComponents";

export default function AuditLogs() {
  const [action, setAction] = useState("");
  const [applied, setApplied] = useState("");
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => get("/admin/audit-logs", { action: applied, page }), [applied, page]);
  return (
    <div className="space-y-6">
      <PageHeader title="Audit logs" subtitle="Record of sign-ins, account changes and administrative actions." />
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(action); }}>
        <input className="input max-w-xs" placeholder="Filter by action, e.g. user. or job." value={action} onChange={(e) => setAction(e.target.value)} aria-label="Action filter" />
        <Button type="submit"><Search size={16} /> Filter</Button>
      </form>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && <>
          <Table rows={data.items} empty="No log entries" columns={[
            { label: "When", render: (r) => fmtDateTime(r.created_at) }, { label: "Actor", render: (r) => r.actor || "—" },
            { label: "Action", render: (r) => <code className="text-xs">{r.action}</code> },
            { label: "Target", render: (r) => r.entity_type ? `${r.entity_type} #${r.entity_id ?? ""}` : "—" },
            { label: "Details", render: (r) => <code className="block max-w-sm truncate text-xs" title={JSON.stringify(r.details)}>{JSON.stringify(r.details)}</code> },
            { label: "IP", render: (r) => r.ip_address || "—" }]} />
          <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
        </>}
      </Card>
    </div>
  );
}
