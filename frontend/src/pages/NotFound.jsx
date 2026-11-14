// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/NotFound.jsx
//
// FILE PURPOSE:
// The 404 page for unknown URLs inside the signed-in app.
//
// WHAT THIS FILE DOES:
// 1. Shows a 'page not found' message with a link home.
//
// HOW THIS FILE WORKS:
// A tiny component rendered by the catch-all route in App.jsx.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: NotFound
//
// INPUT:
// Unknown URL.
//
// OUTPUT:
// 404 message.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/SharedUiComponents.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* 404 page for unknown routes inside the signed-in layout. */

import { Link } from "react-router-dom";
import { EmptyState } from "../components/SharedUiComponents";

export default function NotFound() {
  return <EmptyState title="Page not found" message="The page you're looking for doesn't exist." action={<Link className="inline-flex h-10 items-center rounded-xl px-5 text-sm font-medium bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow hover:brightness-110" to="/">Go to dashboard</Link>} />;
}
