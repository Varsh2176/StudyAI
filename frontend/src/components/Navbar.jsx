import { NavLink } from "react-router-dom";

function Navbar() {
  return (
    <nav className="navbar">
      <NavLink to="/" className="nav-brand">
        <span>🎓</span> StudyWise AI
      </NavLink>
      <div className="nav-links">
        <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Register
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Profile
        </NavLink>
        <NavLink to="/predict" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Predict Score & Risk
        </NavLink>
        <NavLink to="/planner" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Study Planner
        </NavLink>
        <NavLink to="/tutor" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          AI Tutor
        </NavLink>
        <NavLink to="/dashboard" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Dashboard
        </NavLink>
        <NavLink to="/progress" className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
          Progress
        </NavLink>
      </div>
    </nav>
  );
}

export default Navbar;
