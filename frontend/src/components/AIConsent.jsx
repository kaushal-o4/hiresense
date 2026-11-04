/* Hosted-AI data notice. Shown only when the server uses Google Gemini (GET /auth/privacy): a student agrees once,
 * the time is stored on the account (POST /auth/ai-consent), and AI features are blocked until then (HTTP 428). */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { get, post } from "../api";
import { useAuth } from "../auth";
import { Button } from "./ui";

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
