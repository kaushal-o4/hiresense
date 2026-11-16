// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/App.jsx
//
// FILE PURPOSE:
// Defines every page URL (route) of the frontend and makes sure each role only opens its own pages.
//
// MAIN RESPONSIBILITY:
// Routing table and role-based route guard.
//
// WHAT THIS FILE DOES:
// 1. Shows a loading spinner while the login session is being checked.
// 2. Shows only the public pages (login, register, forgot/reset password, privacy) when nobody is
//    logged in.
// 3. For a logged-in user, maps URLs such as /student/interviews or /recruiter/jobs to page
//    components.
// 4. Uses RequireRole so a student cannot open recruiter/mentor/admin pages (they are sent to their
//    own home).
// 5. Redirects old URLs of merged pages to the new tabbed pages.
// 6. Loads most pages lazily (React.lazy) so the first download is small.
//
// HOW THIS FILE WORKS:
// It reads the user from useAuth(). If there is no user, a small route list is used. Otherwise all
// routes are placed inside the AppShellLayout (sidebar + header). Each protected route is wrapped in
// RequireRole which compares user.role with the role required by the page.
//
// IMPORTANT FUNCTIONS:
//    - App()
//        Main component: chooses the signed-out or signed-in route list.
//    - RequireRole()
//        Guard component: renders the page only if the user has the required role, else
//        redirects to the user's home page.
//    Other helper functions: Profile, Notifications, NotFound, Settings, ProgressHub,
//    Opportunities, StudentDashboard, Resume, Interviews, InterviewSession, VoiceInterview,
//    English, EnglishSession, Vocabulary, StudentAssessments, Rewards, Applications, Mentoring,
//    RecruiterDashboard, RecruiterJobs, RecruiterJobDetail, Candidates, CandidateDetail,
//    CompareCandidates, CandidateReport, MentorDashboard, MentorStudents, MentorStudentDetail,
//    MentorSessions, AdminDashboard, AdminUsers, AdminAssignments, AdminJobs, InterviewConfig,
//    AdminRewards, Monitoring, AuditLogs, Reports, AdminSettings, AssessmentManager,
//    IntegrityReviewPage
//
// IMPORTANT VARIABLES / STATE:
//    - HOME
//        Home URL of each role: /student, /recruiter, /mentor, /admin.
//
// INPUT:
// The current user and loading flag from AuthContext, and the browser URL.
//
// OUTPUT:
// The page component that matches the URL.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, components/AppShellLayout.jsx, components/SharedUiComponents.jsx,
//    pages/AccountSettings.jsx, pages/ForgotPassword.jsx, pages/Login.jsx, pages/NotFound.jsx,
//    pages/Notifications.jsx, pages/Privacy.jsx, pages/ProfileEditor.jsx, pages/Register.jsx,
//    pages/ResetPassword.jsx, pages/admin/AdminDashboard.jsx, pages/admin/AdminJobPostings.jsx,
//    pages/admin/AdminMonitoring.jsx, pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx,
//    pages/admin/InterviewConfig.jsx, pages/admin/MentorAssignments.jsx,
//    pages/admin/PlacementReports.jsx, pages/admin/PlatformSettings.jsx,
//    pages/admin/UserManagement.jsx, pages/mentor/MentorDashboard.jsx,
//    pages/mentor/MentorSessions.jsx, pages/mentor/MentorStudentDetail.jsx,
//    pages/mentor/MentorStudentList.jsx, pages/recruiter/CandidateDetail.jsx,
//    pages/recruiter/CandidateReport.jsx, pages/recruiter/CandidateSearch.jsx,
//    pages/recruiter/CompareCandidates.jsx, pages/recruiter/RecruiterDashboard.jsx,
//    pages/recruiter/RecruiterJobApplicants.jsx, pages/recruiter/RecruiterJobPostings.jsx,
//    pages/shared/AssessmentManager.jsx, pages/shared/IntegrityReview.jsx,
//    pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
//    pages/student/InterviewSession.jsx, pages/student/JobApplications.jsx,
//    pages/student/JobsAndDrives.jsx, pages/student/LiveVoiceInterview.jsx,
//    pages/student/MockInterviewHome.jsx, pages/student/ProgressHub.jsx,
//    pages/student/ResumeUploadAndAnalysis.jsx, pages/student/StudentAssessments.jsx,
//    pages/student/StudentDashboard.jsx, pages/student/StudentMentoring.jsx,
//    pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx
//    Used by: main.jsx
//
// EXECUTION FLOW:
//    AuthContext finishes /auth/me check
//       |
//       v
//    No user -> public routes only
//       |
//       v
//    User -> routes inside AppShellLayout
//       |
//       v
//    RequireRole checks the role
//       |
//       v
//    Matching page component is rendered
//
// IMPORTANT DEPENDENCIES:
//    react, react-router-dom
//
// IMPORTANT NOTE:
// This is only a user-interface guard. The real security check is done again by the backend on every
// API call.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Top-level route definitions and role-based guards. */

import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./AuthContext";
import Layout from "./components/AppShellLayout";
import { Spinner } from "./components/SharedUiComponents";

// Signed-out pages load with the app so the login screen appears at once. Every other page is its own chunk,
// downloaded when first opened (Layout wraps the page outlet in <Suspense>).
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Privacy from "./pages/Privacy";
import Landing from "./pages/Landing";

const Profile = lazy(() => import("./pages/ProfileEditor"));
const Notifications = lazy(() => import("./pages/Notifications"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Settings = lazy(() => import("./pages/AccountSettings"));
const ProgressHub = lazy(() => import("./pages/student/ProgressHub"));
const Opportunities = lazy(() => import("./pages/student/JobsAndDrives"));

const StudentDashboard = lazy(() => import("./pages/student/StudentDashboard"));
const Resume = lazy(() => import("./pages/student/ResumeUploadAndAnalysis"));
const Interviews = lazy(() => import("./pages/student/MockInterviewHome"));
const InterviewSession = lazy(() => import("./pages/student/InterviewSession"));
const VoiceInterview = lazy(() => import("./pages/student/LiveVoiceInterview"));
const English = lazy(() => import("./pages/student/EnglishPracticeHome"));
const EnglishSession = lazy(() => import("./pages/student/EnglishSession"));
const Vocabulary = lazy(() => import("./pages/student/VocabularyTrainer"));
const StudentAssessments = lazy(() => import("./pages/student/StudentAssessments"));
const Rewards = lazy(() => import("./pages/student/StudentRewards"));
const Applications = lazy(() => import("./pages/student/JobApplications"));
const Mentoring = lazy(() => import("./pages/student/StudentMentoring"));

const RecruiterDashboard = lazy(() => import("./pages/recruiter/RecruiterDashboard"));
const RecruiterJobs = lazy(() => import("./pages/recruiter/RecruiterJobPostings"));
const RecruiterJobDetail = lazy(() => import("./pages/recruiter/RecruiterJobApplicants"));
const Candidates = lazy(() => import("./pages/recruiter/CandidateSearch"));
const CandidateDetail = lazy(() => import("./pages/recruiter/CandidateDetail"));
const CompareCandidates = lazy(() => import("./pages/recruiter/CompareCandidates"));
const CandidateReport = lazy(() => import("./pages/recruiter/CandidateReport"));

const MentorDashboard = lazy(() => import("./pages/mentor/MentorDashboard"));
const MentorStudents = lazy(() => import("./pages/mentor/MentorStudentList"));
const MentorStudentDetail = lazy(() => import("./pages/mentor/MentorStudentDetail"));
const MentorSessions = lazy(() => import("./pages/mentor/MentorSessions"));

const AdminDashboard = lazy(() => import("./pages/admin/AdminDashboard"));
const AdminUsers = lazy(() => import("./pages/admin/UserManagement"));
const AdminAssignments = lazy(() => import("./pages/admin/MentorAssignments"));
const AdminJobs = lazy(() => import("./pages/admin/AdminJobPostings"));
const InterviewConfig = lazy(() => import("./pages/admin/InterviewConfig"));
const AdminRewards = lazy(() => import("./pages/admin/AdminRewardRules"));
const Monitoring = lazy(() => import("./pages/admin/AdminMonitoring"));
const AuditLogs = lazy(() => import("./pages/admin/AuditLogs"));
const Reports = lazy(() => import("./pages/admin/PlacementReports"));
const AdminSettings = lazy(() => import("./pages/admin/PlatformSettings"));
const AssessmentManager = lazy(() => import("./pages/shared/AssessmentManager"));
const IntegrityReviewPage = lazy(() => import("./pages/shared/IntegrityReview"));

// Home page of each role (where a user lands after login or when opening a page of another role).
const HOME = { student: "/student", recruiter: "/recruiter", mentor: "/mentor", admin: "/admin" };

// Route guard: renders the page only for the given role, otherwise redirects to the user's own home page.
// (The backend checks the role again on every API call; this guard only keeps the UI tidy.)
function RequireRole({ role, children }) {
  const { user } = useAuth();
  if (role && user.role !== role) return <Navigate to={HOME[user.role]} replace />;
  return children;
}

export default function App() {
  const { user, loading } = useAuth();
  // Wait for AuthContext's first /auth/me check before deciding which pages to show.
  if (loading) return <Spinner label="Starting HireSense…" />;

  // Signed out: only the public pages exist; "/" is the marketing landing page, every other URL goes to sign-in.
  if (!user) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  const r = (role, el) => <RequireRole role={role}>{el}</RequireRole>;
  return (
    <Routes>
      <Route path="/login" element={<Navigate to={HOME[user.role]} replace />} />
      <Route path="/register" element={<Navigate to={HOME[user.role]} replace />} />
      <Route path="/forgot-password" element={<Navigate to="/settings" replace />} />
      <Route path="/reset-password" element={<ResetPassword />} />{/* a reset link may be opened while signed in */}
      <Route path="/privacy" element={<Privacy />} />
      <Route path="/home" element={<Landing />} />{/* landing page stays reachable when signed in */}
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to={HOME[user.role]} replace />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/settings" element={<Settings />} />
        {/* speaking drills were removed; old bookmarks go to English conversation practice */}
        <Route path="/student/english-learning" element={<Navigate to="/student/english" replace />} />
        {/* merged pages: old links (bookmarks, notifications) open the matching tab */}
        <Route path="/student/report" element={<Navigate to="/student/progress?tab=report" replace />} />
        <Route path="/student/history" element={<Navigate to="/student/progress?tab=history" replace />} />
        <Route path="/student/drives" element={<Navigate to="/student/jobs?tab=drives" replace />} />

        <Route path="/student" element={r("student", <StudentDashboard />)} />
        <Route path="/student/resume" element={r("student", <Resume />)} />
        <Route path="/student/interviews" element={r("student", <Interviews />)} />
        <Route path="/student/interviews/:id" element={r("student", <InterviewSession />)} />
        <Route path="/student/interviews/:id/live" element={r("student", <VoiceInterview />)} />
        <Route path="/student/english" element={r("student", <English />)} />
        <Route path="/student/english/vocabulary" element={r("student", <Vocabulary />)} />
        <Route path="/student/english/:id" element={r("student", <EnglishSession />)} />
        <Route path="/student/assessments" element={r("student", <StudentAssessments />)} />
        <Route path="/student/progress" element={r("student", <ProgressHub />)} />
        <Route path="/student/rewards" element={r("student", <Rewards />)} />
        <Route path="/student/jobs" element={r("student", <Opportunities />)} />
        <Route path="/student/applications" element={r("student", <Applications />)} />
        <Route path="/student/mentoring" element={r("student", <Mentoring />)} />

        <Route path="/recruiter" element={r("recruiter", <RecruiterDashboard />)} />
        <Route path="/recruiter/jobs" element={r("recruiter", <RecruiterJobs />)} />
        <Route path="/recruiter/jobs/:id" element={r("recruiter", <RecruiterJobDetail />)} />
        <Route path="/recruiter/jobs/:id/compare" element={r("recruiter", <CompareCandidates />)} />
        <Route path="/recruiter/applications/:id/report" element={r("recruiter", <CandidateReport />)} />
        <Route path="/recruiter/candidates" element={r("recruiter", <Candidates />)} />
        <Route path="/recruiter/candidates/:id" element={r("recruiter", <CandidateDetail />)} />
        <Route path="/recruiter/assessments" element={r("recruiter", <AssessmentManager />)} />
        <Route path="/recruiter/security" element={r("recruiter", <IntegrityReviewPage />)} />

        <Route path="/mentor" element={r("mentor", <MentorDashboard />)} />
        <Route path="/mentor/students" element={r("mentor", <MentorStudents />)} />
        <Route path="/mentor/students/:id" element={r("mentor", <MentorStudentDetail />)} />
        <Route path="/mentor/sessions" element={r("mentor", <MentorSessions />)} />
        <Route path="/mentor/integrity" element={r("mentor", <IntegrityReviewPage />)} />

        <Route path="/admin" element={r("admin", <AdminDashboard />)} />
        <Route path="/admin/users" element={r("admin", <AdminUsers />)} />
        <Route path="/admin/assignments" element={r("admin", <AdminAssignments />)} />
        <Route path="/admin/jobs" element={r("admin", <AdminJobs />)} />
        <Route path="/admin/interview-config" element={r("admin", <InterviewConfig />)} />
        <Route path="/admin/assessments" element={r("admin", <AssessmentManager />)} />
        <Route path="/admin/rewards" element={r("admin", <AdminRewards />)} />
        <Route path="/admin/monitoring" element={r("admin", <Monitoring />)} />
        <Route path="/admin/audit" element={r("admin", <AuditLogs />)} />
        <Route path="/admin/reports" element={r("admin", <Reports />)} />
        <Route path="/admin/settings" element={r("admin", <AdminSettings />)} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
