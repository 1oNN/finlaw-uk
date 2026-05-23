import { Link, useLocation } from "react-router-dom";

export default function ChatLaunch() {
  const { pathname } = useLocation();
  if (pathname === "/chat") return null;

  return (
    <Link
      to="/chat"
      className="fixed bottom-6 right-6 grid h-12 w-12 place-items-center rounded-full bg-accent text-white shadow-chat hover:bg-accent-hover"
      title="Open chat"
    >
      💬
    </Link>
  );
}
