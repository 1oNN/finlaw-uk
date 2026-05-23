import React, { createContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export const AuthContext = createContext({
  loggedIn: false,
  setLoggedIn: () => {},
  logout: () => {},
});

const API_BASE = "http://localhost:5000";

export function AuthProvider({ children }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    fetch(`${API_BASE}/login`, { method: "GET", credentials: "include" })
      .then((res) => setLoggedIn(res.ok))
      .catch(() => setLoggedIn(false));
  }, []);

  const logout = () => {
    fetch(`${API_BASE}/logout`, { method: "POST", credentials: "include" })
      .catch(() => {})
      .finally(() => {
        setLoggedIn(false);
        localStorage.removeItem("access_token");
        nav("/login");
      });
  };

  return (
    <AuthContext.Provider value={{ loggedIn, setLoggedIn, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
