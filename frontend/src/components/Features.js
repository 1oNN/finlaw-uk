const features = [
  {
    icon: "📚",
    title: "Grounded answers",
    desc: "Each response cites statutes, FCA rules, or case law—no guess-work.",
  },
  {
    icon: "🔒",
    title: "Private & secure",
    desc: "Runs locally; your data never leaves your device.",
  },
  {
    icon: "🕑",
    title: "Always-on expertise",
    desc: "Ask unlimited follow-up questions, 24/7.",
  },
];

export default function Features() {
  return (
    <section className="bg-gradient-to-b from-[#111318] to-[#0f1217] py-20">
      <div className="container mx-auto max-w-5xl px-6">
        <h2 className="mb-8 text-center text-3xl font-extrabold text-gray-200">
          Why choose this assistant?
        </h2>
        <div className="grid gap-6 md:grid-cols-3">
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-white/15 bg-surface p-5 transition hover:-translate-y-0.5 hover:border-accent"
            >
              <div className="mb-2 text-3xl">{f.icon}</div>
              <h3 className="text-lg font-semibold text-white">{f.title}</h3>
              <p className="mt-2 text-sm text-muted">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
