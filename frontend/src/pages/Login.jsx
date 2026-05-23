import React, { useState, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../components/AuthContext";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setLoggedIn } = useContext(AuthContext);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    const res = await fetch("http://localhost:5000/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (res.ok) {
      setLoggedIn(true);
      navigate("/chat");
    } else {
      const { error } = await res.json();
      setError(error || "Login failed");
    }
  };

  return (
    <div className="max-w-md mx-auto mt-20 p-6 bg-surface rounded-lg shadow">
      <h1 className="text-2xl mb-4">Log In</h1>
      {error && <div className="text-red-400 mb-2">{error}</div>}
      <form onSubmit={submit} className="space-y-4">
        <input
          type="email"
          placeholder="Email"
          className="w-full p-2 border rounded"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          className="w-full p-2 border rounded"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button className="w-full py-2 bg-accent text-white rounded">
          Log In
        </button>
      </form>
    </div>
  );
}
