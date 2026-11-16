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

import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Compass } from "lucide-react";
import { Button, buttonClass } from "../components/SharedUiComponents";

export default function NotFound() {
  const navigate = useNavigate();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 py-16 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 shadow-soft"><Compass size={22} strokeWidth={1.8} /></span>
      <p className="num mt-6 font-display text-[13px] font-bold tracking-[0.2em] text-brand-600">ERROR 404</p>
      <h1 className="mt-2 text-[30px] font-bold tracking-tight text-slate-950 sm:text-[36px]">Page not found</h1>
      <p className="mt-3 max-w-md text-[15px] leading-relaxed text-slate-500">
        The page you’re looking for doesn’t exist or has moved. Check the address, or head back to your dashboard.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        <Button variant="secondary" onClick={() => navigate(-1)}><ArrowLeft size={15} /> Go back</Button>
        <Link className={buttonClass("primary")} to="/">Go to dashboard</Link>
      </div>
    </div>
  );
}
