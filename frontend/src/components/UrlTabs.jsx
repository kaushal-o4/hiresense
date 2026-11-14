// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/UrlTabs.jsx
//
// FILE PURPOSE:
// Tabs whose selected tab is kept in the page URL (?tab=...), so tabs can be linked and the back
// button works.
//
// WHAT THIS FILE DOES:
// 1. Reads ?tab= from the URL.
// 2. Shows the tab buttons and the active tab's content.
// 3. Updates the URL when a tab is clicked.
//
// HOW THIS FILE WORKS:
// Uses React Router's useSearchParams. The first tab is the default and has no ?tab parameter.
//
// IMPORTANT FUNCTIONS:
//    - UrlTabs()
//        Renders tab buttons and the selected tab panel.
//
// INPUT:
// Props: tabs [{id, label, element}], label.
//
// OUTPUT:
// Tab bar and active panel.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: pages/student/JobsAndDrives.jsx, pages/student/ProgressHub.jsx
//
// IMPORTANT DEPENDENCIES:
//    react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* URL-backed page tabs (?tab=...), used by the merged "My Progress" and "Jobs & Drives" pages. */

import { useSearchParams } from "react-router-dom";

/**
 * Page-level tabs kept in the URL (?tab=...), so every tab can be linked to and the back button works.
 * tabs: [{ id, label, element }]; the first tab is the default.
 */
export default function UrlTabs({ tabs, label }) {
  const [params, setParams] = useSearchParams();
  const active = tabs.find((t) => t.id === params.get("tab")) || tabs[0];
  const select = (id) => setParams(id === tabs[0].id ? {} : { tab: id }, { replace: true });
  return (
    <div className="space-y-6">
      <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-slate-200 print:hidden">
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" aria-selected={t.id === active.id} onClick={() => select(t.id)}
            className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition ${t.id === active.id
              ? "border-slate-900 text-slate-900" : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-800"}`}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">{active.element}</div>
    </div>
  );
}
