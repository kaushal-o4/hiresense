// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/PlacementDrives.jsx
//
// FILE PURPOSE:
// Campus placement drives for students.
//
// WHAT THIS FILE DOES:
// 1. Lists drives (GET /student/drives).
// 2. Registers (POST /student/drives/{id}/register) or cancels (DELETE ...).
//
// HOW THIS FILE WORKS:
// A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with
// useState and sends changes with post/put/patch/del, then shows results with the shared UI
// components. API calls used: GET /student/drives, POST/DELETE /student/drives/{id}/register.
//
// IMPORTANT FUNCTIONS:
//    - StudentDrives()
//        Page component.
//
// INPUT:
// Drive list.
//
// OUTPUT:
// Registration status.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx
//    Used by: pages/student/JobsAndDrives.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Campus placement drives: register or cancel a registration. Shown as a tab of Opportunities. */

import { CalendarDays, MapPin } from "lucide-react";
import { del, get, post } from "../../apiClient";
import { Button, Card, EmptyState, ErrorBox, PageHeader, Pill, SectionHeader, Spinner, StatusPill, fmtDateTime, useApi, useToast } from "../../components/SharedUiComponents";

export default function StudentDrives({ embedded = false }) {
  const Header = embedded ? SectionHeader : PageHeader;
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => get("/student/drives"));
  const act = async (fn, msg) => { try { await fn(); toast(msg); reload(); } catch (e) { toast(e.message, "error"); } };
  return (
    <div className="space-y-6">
      <Header title="Placement drives" subtitle="Campus recruitment drives organised by the placement office." />
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data?.length === 0 && <Card><EmptyState icon={CalendarDays} title="No placement drives announced yet" /></Card>}
      <div className="grid gap-4 md:grid-cols-2">
        {data?.map((d) => (
          <Card key={d.id}>
            <div className="flex items-start justify-between gap-2">
              <div><h3 className="font-semibold">{d.title}</h3><p className="text-sm text-slate-600">{d.company_name}</p></div>
              <StatusPill status={d.status === "upcoming" ? "scheduled" : d.status} />
            </div>
            <p className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500"><span><CalendarDays size={12} className="mr-1 inline" />{fmtDateTime(d.drive_date)}</span>{d.location && <span><MapPin size={12} className="mr-1 inline" />{d.location}</span>}</p>
            {d.description && <p className="mt-2 whitespace-pre-line text-sm text-slate-600">{d.description}</p>}
            <p className="mt-2 text-xs text-slate-500">Eligibility: CGPA {d.min_cgpa ?? "any"} · {d.eligible_branches.length ? d.eligible_branches.join(", ") : "all branches"}</p>
            <div className="mt-4 flex items-center justify-between">
              {d.registered ? <Pill tone="green">Registered</Pill> : !d.eligible ? <span className="text-xs text-red-700">Not eligible: {d.ineligible_reasons.join("; ")}</span> : <span />}
              {d.status === "upcoming" && (d.registered
                ? <Button size="sm" variant="ghost" onClick={() => act(() => del(`/student/drives/${d.id}/register`), "Registration cancelled")}>Cancel registration</Button>
                : d.eligible && <Button size="sm" onClick={() => act(() => post(`/student/drives/${d.id}/register`), "Registered for the drive")}>Register</Button>)}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
