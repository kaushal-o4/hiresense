// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/JobsAndDrives.jsx
//
// FILE PURPOSE:
// 'Jobs & drives' area with two URL tabs.
//
// WHAT THIS FILE DOES:
// 1. Shows StudentJobOpenings and PlacementDrives as tabs.
//
// HOW THIS FILE WORKS:
// Only arranges child pages in UrlTabs.
//
// IMPORTANT FUNCTIONS:
//    - Opportunities()
//        Page component.
//
// INPUT:
// URL ?tab=.
//
// OUTPUT:
// Tabbed page.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/UrlTabs.jsx, pages/student/PlacementDrives.jsx,
//    pages/student/StudentJobOpenings.jsx
//    Used by: App.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* "Jobs & Drives" menu item: the Jobs and Drives pages as URL tabs. */

import UrlTabs from "../../components/UrlTabs";
import StudentDrives from "./PlacementDrives";
import Jobs from "./StudentJobOpenings";

// Job openings and campus placement drives in one place (previously two menu items).
export default function Opportunities() {
  return (
    <UrlTabs label="Opportunities" title="Job opportunities" subtitle="Openings matched to your skills, and campus drives from the placement office." tabs={[
      { id: "jobs", label: "Job openings", element: <Jobs embedded /> },
      { id: "drives", label: "Placement drives", element: <StudentDrives embedded /> },
    ]} />
  );
}
