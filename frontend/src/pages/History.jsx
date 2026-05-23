import { useState, useEffect } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";

const api = axios.create({
  baseURL: "http://localhost:5000",
});
api.interceptors.request.use((cfg) => {
  cfg.headers.Authorization = `Bearer ${localStorage.getItem("access_token")}`;
  return cfg;
});

export default function History() {
  const [chats, setChats] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    api.get("/api/chats").then((res) => setChats(res.data));
  }, []);

  return (
    <div className="max-w-2xl mx-auto mt-10 p-6 bg-surface rounded-lg">
      <h1 className="text-2xl mb-4">Chat History</h1>
      {chats.length === 0 && <p>No chats yet.</p>}
      <ul className="space-y-2">
        {chats.map((c) => (
          <li key={c.id}>
            <button
              className="text-left w-full p-2 border rounded hover:bg-surface/50"
              onClick={() => nav(`/chat?history=${c.id}`)}
            >
              Chat #{c.id} — {new Date(c.started).toLocaleString()}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
