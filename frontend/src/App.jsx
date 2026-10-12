import { lazy, Suspense } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import AuthLayout from "./components/AuthLayout";
import AppShell from "./components/AppShell";
import Register from "./pages/Register";
import StudentProfile from "./pages/StudentProfile";
import PredictScore from "./pages/PredictScore";
import StudyPlanner from "./pages/StudyPlanner";
import AiTutor from "./pages/AiTutor";
import Dashboard from "./pages/Dashboard";
import ProgressTracking from "./pages/ProgressTracking";
import Documents from "./pages/Documents";
import "./styles/tokens.css";
import "./styles.css";
import "./styles/shell.css";
import "./styles/ui.css";
import "./styles/dashboard.css";
import "./styles/planner.css";
import "./styles/progress.css";
import "./styles/tutor.css";
import "./styles/documents.css";

/** Temporary DEV-only gallery — remove route in Phase 7. */
const UiPreview = import.meta.env.DEV
  ? lazy(() => import("./pages/UiPreview.jsx"))
  : null;

function App() {
  return (
    <Router>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/" element={<Register />} />
        </Route>

        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/predict" element={<PredictScore />} />
          <Route path="/planner" element={<StudyPlanner />} />
          <Route path="/tutor" element={<AiTutor />} />
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
      </Routes>
    </Router>
  );
}

export default App;
