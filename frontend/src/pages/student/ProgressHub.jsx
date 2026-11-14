// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/ProgressHub.jsx
//
// FILE PURPOSE:
// 'My progress' area with three URL tabs.
//
// WHAT THIS FILE DOES:
// 1. Combines ProgressOverview, PerformanceReport and PracticeHistory with UrlTabs.
//
// HOW THIS FILE WORKS:
// Only arranges child pages in UrlTabs.
//
// IMPORTANT FUNCTIONS:
//    - ProgressHub()
//        One "My Progress" area instead of three separate menu items (Progress, Performance
//        Report, Practice History).
//
// INPUT:
// URL ?tab=.
//
// OUTPUT:
// Tabbed page.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/UrlTabs.jsx, pages/student/PerformanceReport.jsx,
//    pages/student/PracticeHistory.jsx, pages/student/ProgressOverview.jsx
//    Used by: App.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* "My Progress" menu item: Overview, Full report and Practice history as URL tabs. */

import UrlTabs from "../../components/UrlTabs";
import PerformanceReport from "./PerformanceReport";
import PracticeHistory from "./PracticeHistory";
import Progress from "./ProgressOverview";

// One "My Progress" area instead of three separate menu items (Progress, Performance Report, Practice History).
export default function ProgressHub() {
  return (
    <UrlTabs label="My progress" tabs={[
      { id: "overview", label: "Overview", element: <Progress /> },
      { id: "report", label: "Full report", element: <PerformanceReport /> },
      { id: "history", label: "Practice history", element: <PracticeHistory /> },
    ]} />
  );
}
