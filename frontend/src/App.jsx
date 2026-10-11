import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Register from "./pages/Register";
import StudentProfile from "./pages/StudentProfile";
import PredictScore from "./pages/PredictScore";
import StudyPlanner from "./pages/StudyPlanner";
import AiTutor from "./pages/AiTutor";
import Dashboard from "./pages/Dashboard";
import ProgressTracking from "./pages/ProgressTracking";
import Documents from "./pages/Documents";
import "./styles.css";

function App() {
  return (
    <Router>
      <div className="app-container">
        <Navbar />
        <Routes>
          <Route path="/" element={<Register />} />
          <Route path="/profile" element={<StudentProfile />} />
          <Route path="/predict" element={<PredictScore />} />
          <Route path="/planner" element={<StudyPlanner />} />
          <Route path="/tutor" element={<AiTutor />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/progress" element={<ProgressTracking />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
