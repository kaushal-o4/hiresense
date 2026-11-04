/* Top-level route definitions and role-based guards. */

import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";

import Login from "./pages/Login";
import Register from "./pages/Register";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import Profile from "./pages/Profile";
import Notifications from "./pages/Notifications";
import NotFound from "./pages/NotFound";
import Settings from "./pages/Settings";
import ProgressHub from "./pages/student/ProgressHub";
import Opportunities from "./pages/student/Opportunities";

import StudentDashboard from "./pages/student/Dashboard";
import Resume from "./pages/student/Resume";
import Interviews from "./pages/student/Interviews";
import InterviewSession from "./pages/student/InterviewSession";
import VoiceInterview from "./pages/student/VoiceInterview";
import English from "./pages/student/English";
import EnglishSession from "./pages/student/EnglishSession";
import StudentAssessments from "./pages/student/Assessments";
import Rewards from "./pages/student/Rewards";
import Applications from "./pages/student/Applications";
import Mentoring from "./pages/student/Mentoring";

import RecruiterDashboard from "./pages/recruiter/Dashboard";
import RecruiterJobs from "./pages/recruiter/Jobs";
import RecruiterJobDetail from "./pages/recruiter/JobDetail";
import Candidates from "./pages/recruiter/Candidates";
import CandidateDetail from "./pages/recruiter/CandidateDetail";
import CompareCandidates from "./pages/recruiter/CompareCandidates";
import CandidateReport from "./pages/recruiter/CandidateReport";

import MentorDashboard from "./pages/mentor/Dashboard";
import MentorStudents from "./pages/mentor/Students";
import MentorStudentDetail from "./pages/mentor/StudentDetail";
import MentorSessions from "./pages/mentor/Sessions";

import AdminDashboard from "./pages/admin/Dashboard";
import AdminUsers from "./pages/admin/Users";
import AdminAssignments from "./pages/admin/Assignments";
import AdminJobs from "./pages/admin/Jobs";
import InterviewConfig from "./pages/admin/InterviewConfig";
import AdminRewards from "./pages/admin/Rewards";
import Monitoring from "./pages/admin/Monitoring";
import AuditLogs from "./pages/admin/AuditLogs";
import Reports from "./pages/admin/Reports";
import AdminSettings from "./pages/admin/Settings";
import AssessmentManager from "./pages/shared/AssessmentManager";
import IntegrityReviewPage from "./pages/shared/IntegrityReview";

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
