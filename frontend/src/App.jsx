/* Top-level route definitions and role-based guards. */

import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";

// Signed-out pages load with the app so the login screen appears at once. Every other page is its own chunk,
// downloaded when first opened (Layout wraps the page outlet in <Suspense>).
import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";

const Profile = lazy(() => import("./pages/Profile"));
const Notifications = lazy(() => import("./pages/Notifications"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Settings = lazy(() => import("./pages/Settings"));
const ProgressHub = lazy(() => import("./pages/student/ProgressHub"));
const Opportunities = lazy(() => import("./pages/student/Opportunities"));

const StudentDashboard = lazy(() => import("./pages/student/Dashboard"));
const Resume = lazy(() => import("./pages/student/Resume"));
const Interviews = lazy(() => import("./pages/student/Interviews"));
const InterviewSession = lazy(() => import("./pages/student/InterviewSession"));
const VoiceInterview = lazy(() => import("./pages/student/VoiceInterview"));
const English = lazy(() => import("./pages/student/English"));
const EnglishSession = lazy(() => import("./pages/student/EnglishSession"));
const StudentAssessments = lazy(() => import("./pages/student/Assessments"));
const Rewards = lazy(() => import("./pages/student/Rewards"));
const Applications = lazy(() => import("./pages/student/Applications"));
const Mentoring = lazy(() => import("./pages/student/Mentoring"));

const RecruiterDashboard = lazy(() => import("./pages/recruiter/Dashboard"));
const RecruiterJobs = lazy(() => import("./pages/recruiter/Jobs"));
const RecruiterJobDetail = lazy(() => import("./pages/recruiter/JobDetail"));
const Candidates = lazy(() => import("./pages/recruiter/Candidates"));
const CandidateDetail = lazy(() => import("./pages/recruiter/CandidateDetail"));

const MentorDashboard = lazy(() => import("./pages/mentor/Dashboard"));
const MentorStudents = lazy(() => import("./pages/mentor/Students"));
const MentorStudentDetail = lazy(() => import("./pages/mentor/StudentDetail"));
const MentorSessions = lazy(() => import("./pages/mentor/Sessions"));

const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const AdminUsers = lazy(() => import("./pages/admin/Users"));
const AdminAssignments = lazy(() => import("./pages/admin/Assignments"));
const AdminJobs = lazy(() => import("./pages/admin/Jobs"));
const InterviewConfig = lazy(() => import("./pages/admin/InterviewConfig"));
const AdminRewards = lazy(() => import("./pages/admin/Rewards"));
const Monitoring = lazy(() => import("./pages/admin/Monitoring"));
const AuditLogs = lazy(() => import("./pages/admin/AuditLogs"));
const Reports = lazy(() => import("./pages/admin/Reports"));
const AdminSettings = lazy(() => import("./pages/admin/Settings"));
const AssessmentManager = lazy(() => import("./pages/shared/AssessmentManager"));
const IntegrityReviewPage = lazy(() => import("./pages/shared/IntegrityReview"));

const HOME = { student: "/student", recruiter: "/recruiter", mentor: "/mentor", admin: "/admin" };

function RequireRole({ role, children }) {
  const { user } = useAuth();
  if (role && user.role !== role) return <Navigate to={HOME[user.role]} replace />;
  return children;
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner label="Starting HireSense…" />;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
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
