import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function GoogleCallback() {
  const nav = useNavigate();

  useEffect(() => {
    // parse the JSON returned by your backend
    fetch(`${process.env.REACT_APP_API_BASE}/login/google/authorized`, {
      credentials: "include",
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.access_token) {
          localStorage.setItem("access_token", data.access_token);
          nav("/chat");
        } else {
          // error field?
          nav("/login");
        }
      })
      .catch(() => nav("/login"));
  }, [nav]);

  return <div className="p-6 text-center">Signing you in…</div>;
}
