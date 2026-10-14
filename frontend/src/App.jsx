import { lazy, Suspense } from "react";
import { BrowserRouter as Router, Navigate, Route, Routes } from "react-router-dom";
import AuthLayout from "./components/AuthLayout";
import AppShell from "./components/AppShell";
import { AuthProvider } from "./auth/AuthProvider.jsx";
import ProtectedRoute from "./auth/ProtectedRoute";
import Register from "./pages/Register";
import Login from "./pages/Login";
import StudentProfile from "./pages/StudentProfile";
import PredictScore from "./pages/PredictScore";
import StudyPlanner from "./pages/StudyPlanner";
import Dashboard from "./pages/Dashboard";
import ProgressTracking from "./pages/ProgressTracking";
import Documents from "./pages/Documents";
import LearningHub from "./pages/LearningHub";
import SummaryNotes from "./pages/hub/SummaryNotes";
import Flashcards from "./pages/hub/Flashcards";
import MindMapTool from "./pages/hub/MindMapTool";
import PracticeQuestions from "./pages/hub/PracticeQuestions";
import MockExam from "./pages/hub/MockExam";
import "./styles/tokens.css";
import "./styles.css";
import "./styles/shell.css";
import "./styles/ui.css";
import "./styles/dashboard.css";
import "./styles/planner.css";
import "./styles/progress.css";
import "./styles/documents.css";
import "./styles/forms.css";
import "./styles/hub.css";

/** Temporary DEV-only gallery — remove route in Phase 7. */
const UiPreview = import.meta.env.DEV
  ? lazy(() => import("./pages/UiPreview.jsx"))
  : null;

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/" element={<Register />} />
            <Route path="/login" element={<Login />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/hub" element={<LearningHub />} />
              <Route path="/hub/summary" element={<SummaryNotes />} />
              <Route path="/hub/flashcards" element={<Flashcards />} />
              <Route path="/hub/mindmap" element={<MindMapTool />} />
              <Route path="/hub/practice" element={<PracticeQuestions />} />
              <Route path="/hub/mock-exam" element={<MockExam />} />
              <Route path="/predict" element={<PredictScore />} />
              <Route path="/planner" element={<StudyPlanner />} />
              {/* Legacy /tutor chat page removed — Learning Hub tools use POST /ai/tutor. */}
              <Route path="/tutor" element={<Navigate to="/hub" replace />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/progress" element={<ProgressTracking />} />
              <Route path="/profile" element={<StudentProfile />} />
              {UiPreview ? (
                <Route
                  path="/__ui"
                  element={
                    <Suspense fallback={<p style={{ padding: "1rem" }}>Loading UI preview…</p>}>
                      <UiPreview />
                    </Suspense>
                  }
                />
              ) : null}
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
