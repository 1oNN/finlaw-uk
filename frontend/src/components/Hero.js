import { motion } from "framer-motion";

export default function Hero() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true }}
      className="bg-gradient-to-b from-[#12151b] to-[#0f1115] py-24 text-center"
    >
      <div className="container mx-auto max-w-5xl px-6">
        <h1 className="mb-3 text-4xl font-extrabold text-white">
          AI-Powered Legal &amp; Finance Answers
          <br />
          in Seconds
        </h1>
        <p className="mx-auto max-w-2xl text-gray-400">
          Our assistant combines cutting-edge language models with curated UK
          &amp; EU regulations to deliver reliable answers — 24 / 7.
        </p>
        <a
          href="/chat"
          className="mt-5 inline-flex items-center rounded-lg bg-accent px-5 py-2.5 font-semibold text-white hover:bg-accent-hover"
        >
          Try the Chatbot
        </a>
      </div>
    </motion.section>
  );
}
