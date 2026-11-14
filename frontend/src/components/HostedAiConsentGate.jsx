// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/HostedAiConsentGate.jsx
//
// FILE PURPOSE:
// Asks a student to agree to the AI data notice when the server uses the hosted Google Gemini AI.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /auth/privacy once (cached) to know if consent is required.
// 2. Shows a notice with an 'I agree' button only to students who have not agreed yet.
// 3. Saves consent with POST /auth/ai-consent and updates the user.
//
// HOW THIS FILE WORKS:
// usePrivacyInfo() caches the privacy info in a module variable. AIConsentGate returns nothing when
// consent is not needed or already given.
//
// IMPORTANT FUNCTIONS:
//    - usePrivacyInfo()
//        Hook that loads and caches /auth/privacy.
//    - AIConsentGate()
//        The consent card shown before AI features.
//
// INPUT:
// Logged-in user; /auth/privacy response.
//
// OUTPUT:
// Consent card, or nothing.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, apiClient.js, components/SharedUiComponents.jsx
//    Used by: pages/AccountSettings.jsx, pages/Privacy.jsx, pages/Register.jsx,
//    pages/student/EnglishPracticeHome.jsx, pages/student/MockInterviewHome.jsx,
//    pages/student/ResumeUploadAndAnalysis.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react, react-router-dom
//
// IMPORTANT NOTE:
// With the local Ollama AI nothing leaves the server, so no consent is asked.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Hosted-AI data notice. Shown only when the server uses Google Gemini (GET /auth/privacy): a student agrees once,
 * the time is stored on the account (POST /auth/ai-consent), and AI features are blocked until then (HTTP 428). */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { get, post } from "../apiClient";
import { useAuth } from "../AuthContext";
import { Button } from "./SharedUiComponents";

let cached = null; // the server's privacy info does not change while the page is open

export function usePrivacyInfo() {
  const [info, setInfo] = useState(cached);
  useEffect(() => {
    if (cached) return;
    get("/auth/privacy").then((d) => { cached = d; setInfo(d); }).catch(() => setInfo({ consent_required: false }));
  }, []);
  return info;
}

/** Card with the notice and an "I agree" button; renders nothing when no consent is needed or it was given. */
export default function AIConsentGate({ action = "use the AI features" }) {
  const { user, setUser } = useAuth();
  const info = usePrivacyInfo();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  if (!info?.consent_required || user?.role !== "student" || user?.ai_data_consent_at) return null;

  const agree = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await post("/auth/ai-consent", { accept: true });
      setUser(res.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div role="region" aria-label="AI data notice" className="card mb-6 border border-amber-300/40 p-5">
      <div className="flex items-start gap-3">
        <ShieldCheck size={20} className="mt-0.5 shrink-0 text-amber-500" aria-hidden="true" />
        <div className="space-y-3 text-sm">
          <p className="font-semibold text-slate-900">Before you {action}: your data is processed by Google</p>
          <p className="text-slate-600">{info.notice}</p>
          {error && <p className="text-red-600">{error}</p>}
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={agree} loading={busy}>I agree</Button>
            <Link to="/privacy" className="text-brand-600 hover:underline">Read the privacy notice</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
