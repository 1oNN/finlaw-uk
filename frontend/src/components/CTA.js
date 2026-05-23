import { Link } from "react-router-dom";

export default function CTA() {
  return (
    <section className="bg-gradient-to-r from-emerald-500 to-indigo-600 py-16 text-white">
      <div className="container mx-auto max-w-5xl px-6 text-center">
        <h2 className="mb-3 text-3xl font-extrabold">
          Ready to get answers in seconds?
        </h2>
        <Link
          to="/chat"
          className="inline-flex items-center rounded-lg bg-black px-5 py-2.5 font-semibold hover:bg-black/80"
        >
          Open Chat
        </Link>
      </div>
    </section>
  );
}
