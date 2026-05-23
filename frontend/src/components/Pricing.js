import { motion } from "framer-motion";

export default function Pricing() {
  const plans = [
    {
      name: "Starter",
      price: "£0",
      desc: "20 questions / mo\nCommunity support",
    },
    {
      name: "Pro",
      price: "£29",
      desc: "Unlimited questions\nPriority e-mail support",
      highlight: true,
    },
    {
      name: "Enterprise",
      price: "Custom",
      desc: "Dedicated model instance\nSLA & on-prem options",
    },
  ];

  return (
    <section id="pricing" className="border-t border-white/10 bg-bg py-20">
      <div className="container mx-auto max-w-5xl px-6 text-center">
        <h2 className="mb-6 text-3xl font-extrabold text-gray-200">
          Simple, transparent pricing
        </h2>
        <div className="grid gap-6 md:grid-cols-3">
          {plans.map((p) => (
            <motion.div key={p.name} whileHover={{ y: -6, scale: 1.02 }}>
              <div
                className={`rounded-2xl border p-6 text-left ${
                  p.highlight
                    ? "border-accent bg-surface ring-1 ring-accent/40"
                    : "border-white/15 bg-surface"
                }`}
              >
                <h3 className="mb-2 text-lg font-semibold text-white">
                  {p.name}
                </h3>
                <p className="mb-4 text-4xl font-extrabold text-accent">
                  {p.price}
                </p>
                <pre className="whitespace-pre-wrap text-gray-300">
                  {p.desc}
                </pre>
                <a
                  href="/chat"
                  className="mt-4 inline-flex items-center rounded-lg bg-accent px-4 py-2 font-semibold text-white hover:bg-accent-hover"
                >
                  {p.name === "Starter" ? "Start free" : "Get started"}
                </a>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
