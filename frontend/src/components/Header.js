// src/components/Header.jsx
import React, { useContext } from "react";
import { Link, NavLink } from "react-router-dom";
import { FaBalanceScale } from "react-icons/fa";
import { AuthContext } from "./AuthContext";

export default function Header() {
  const { loggedIn, logout } = useContext(AuthContext);

  return (
    <header className="header">
      <Link to="/" className="brand">
        <FaBalanceScale style={{ color: "var(--accent)" }} />
        <span style={{ fontWeight: 800, letterSpacing: 0.3 }}>LEGAL GPT</span>
      </Link>

      <nav className="nav">
        <NavLink
          to="/"
          end
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Home
        </NavLink>
        <NavLink
          to="/chat"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Chat
        </NavLink>
        <NavLink
          to="/eval"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Evaluation
        </NavLink>
        <NavLink
          to="/pricing"
          className={({ isActive }) => (isActive ? "active" : "")}
        >
          Pricing
        </NavLink>
        {!loggedIn ? (
          <>
            <NavLink
              to="/login"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Log in
            </NavLink>
            <NavLink
              to="/signup"
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              Sign up
            </NavLink>
          </>
        ) : (
          <button onClick={logout}>Log out</button>
        )}
      </nav>
    </header>
  );
}
