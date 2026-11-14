// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/apiClient.js
//
// FILE PURPOSE:
// One small helper used by every page to talk to the backend API.
//
// MAIN RESPONSIBILITY:
// HTTP client (wrapper around fetch) for all /api calls.
//
// WHAT THIS FILE DOES:
// 1. Builds the full URL (/api + path, plus query parameters).
// 2. Sends JSON or file uploads (FormData) with the login cookie included.
// 3. Turns the backend's error message into a readable ApiError.
// 4. Fires a global 'hs:unauthorized' event when the session has expired (HTTP 401).
// 5. Offers short helpers get/post/put/patch/del and a download() helper for files.
//
// HOW THIS FILE WORKS:
// api() calls the browser fetch() with credentials: 'include', so the httpOnly session cookie set by
// the backend is sent automatically; no token is stored in JavaScript. The response text is parsed as
// JSON. If the status is not OK, an ApiError with the status and message is thrown. API_BASE allows
// the API to be on a different domain.
//
// IMPORTANT FUNCTIONS:
//    - api()
//        Core request function: builds URL, sends request, parses response, throws ApiError on
//        failure.
//    - get()
//        GET request with optional query parameters.
//    - post()
//        POST request with a JSON or FormData body.
//    - put()
//        PUT request.
//    - patch()
//        PATCH request.
//    - del()
//        DELETE request.
//    - download()
//        Downloads a file (e.g. resume or CSV) and saves it in the browser.
//    - apiUrl()
//        Adds VITE_API_URL in front of an /api path when the API is hosted elsewhere.
//    - formatDetail()
//        Turns FastAPI validation errors into a readable message.
//    Other helper functions: ApiError
//
// IMPORTANT VARIABLES / STATE:
//    - API_BASE
//        Optional backend address from VITE_API_URL (empty = same site).
//
// INPUT:
// A path such as '/student/dashboard', an optional body and query parameters.
//
// OUTPUT:
// The parsed JSON response, or an ApiError.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: AuthContext.jsx, components/AppShellLayout.jsx, components/EnglishDailyPlan.jsx,
//    components/EnglishMistakeProfile.jsx, components/EnglishProgress.jsx,
//    components/HostedAiConsentGate.jsx, live/notificationStream.js,
//    monitoring/InterviewMonitorBar.jsx, monitoring/eventReporter.js, monitoring/mediaSession.js,
//    monitoring/useTypedMonitoring.js, pages/AccountSettings.jsx, pages/ForgotPassword.jsx,
//    pages/Notifications.jsx, pages/ProfileEditor.jsx, pages/Register.jsx, pages/ResetPassword.jsx,
//    pages/admin/AdminDashboard.jsx, pages/admin/AdminJobPostings.jsx,
//    pages/admin/AdminMonitoring.jsx, pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx,
//    pages/admin/InterviewConfig.jsx, pages/admin/MentorAssignments.jsx,
//    pages/admin/PlacementReports.jsx, pages/admin/PlatformSettings.jsx,
//    pages/admin/SecuritySettings.jsx, pages/admin/UserManagement.jsx,
//    pages/mentor/MentorDashboard.jsx, pages/mentor/MentorSessions.jsx,
//    pages/mentor/MentorStudentDetail.jsx, pages/mentor/MentorStudentList.jsx,
//    pages/recruiter/CandidateDetail.jsx, pages/recruiter/CandidateReport.jsx,
//    pages/recruiter/CandidateSearch.jsx, pages/recruiter/CompareCandidates.jsx,
//    pages/recruiter/RecruiterDashboard.jsx, pages/recruiter/RecruiterJobApplicants.jsx,
//    pages/recruiter/RecruiterJobPostings.jsx, pages/shared/AssessmentManager.jsx,
//    pages/shared/IntegrityReview.jsx, pages/student/EnglishAvatarSession.jsx,
//    pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
//    pages/student/InterviewSession.jsx, pages/student/InterviewSetup.jsx,
//    pages/student/InterviewerFeedback.jsx, pages/student/InterviewerPicker.jsx,
//    pages/student/JobApplications.jsx, pages/student/LiveVoiceInterview.jsx,
//    pages/student/MockInterviewHome.jsx, pages/student/PerformanceReport.jsx,
//    pages/student/PlacementDrives.jsx, pages/student/PracticeHistory.jsx,
//    pages/student/ProgressOverview.jsx, pages/student/ResumeUploadAndAnalysis.jsx,
//    pages/student/StudentAssessments.jsx, pages/student/StudentDashboard.jsx,
//    pages/student/StudentJobOpenings.jsx, pages/student/StudentMentoring.jsx,
//    pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx, voice/turnStream.js,
//    voice/useInterviewers.js
//    Tested by: monitoring/interviewSecurity.test.js
//
// EXECUTION FLOW:
//    Page calls get('/student/dashboard')
//       |
//       v
//    api() builds /api/student/dashboard
//       |
//       v
//    fetch() sends request with cookie
//       |
//       v
//    Backend replies with JSON
//       |
//       v
//    Data returned to the page (or ApiError thrown)
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* HireSense frontend API client and request helpers. */

// Thin fetch wrapper. Auth is an httpOnly cookie set by the backend, so no token is stored in JS.

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

function formatDetail(detail) {
  if (!detail) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = (e.loc || []).filter((p) => p !== "body").join(" → ");
        const msg = (e.msg || "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("\n");
  }
  return JSON.stringify(detail);
}

// Empty (default): the API is on this same site (/api via the Vite proxy, a Vercel rewrite or nginx), so the login
// cookie is first-party. VITE_API_URL=https://api.example.com when the API is on another domain (then the backend
// needs COOKIE_SAMESITE=none, COOKIE_SECURE=true and this site in CORS_ORIGINS).
export const API_BASE = (import.meta.env?.VITE_API_URL || "").replace(/\/+$/, "");
export const apiUrl = (p) => (API_BASE && p.startsWith("/api") ? API_BASE + p : p);

// The one function every page uses to call the backend. `path` is written without "/api" (e.g. "/student/dashboard").
// Returns the parsed JSON, or throws ApiError with a readable message when the server answers with an error.
export async function api(path, { method = "GET", body, params, raw = false } = {}) {
  let url = apiUrl(`/api${path}`);
  // Add query-string parameters, skipping empty values (used by filters and pagination).
  if (params) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.append(k, v);
    });
    const s = qs.toString();
    if (s) url += `?${s}`;
  }
  // credentials: "include" makes the browser send the httpOnly login cookie with every request.
  const opts = { method, credentials: "include", headers: {} };
  // File uploads (FormData) are sent as-is; any other body is sent as JSON.
  if (body instanceof FormData) {
    opts.body = body;
  } else if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (raw && res.ok) return res;
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    // FastAPI puts the error text in `detail` (a list of field errors for 422 validation errors).
    const message = formatDetail(data?.detail) || `Request failed (${res.status})`;
    // 401 = the session expired: tell AuthContext.jsx, which signs the user out and shows the login page.
    if (res.status === 401 && path !== "/auth/me" && path !== "/auth/login") {
      window.dispatchEvent(new Event("hs:unauthorized"));
    }
    throw new ApiError(message, res.status, data);
  }
  return data;
}

export const get = (p, params) => api(p, { params });
export const post = (p, body) => api(p, { method: "POST", body });
export const put = (p, body) => api(p, { method: "PUT", body });
export const patch = (p, body) => api(p, { method: "PATCH", body });
export const del = (p) => api(p, { method: "DELETE" });

export async function download(path, filename) {
  const res = await api(path, { raw: true });
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
