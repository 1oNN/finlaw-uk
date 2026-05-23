import React from "react";
import { Link } from "react-router-dom";
import {
  FiArrowRight,
  FiCheck,
  FiShield,
  FiCpu,
  FiBookOpen,
  FiGitBranch,
  FiLock,
} from "react-icons/fi";
import Header from "../components/Header";
import Footer from "../components/Footer";
import DisclaimerBand from "../components/DisclaimerBand";
import StatuteBadge from "../components/StatuteBadge";
import Logo from "../components/Logo";

const STATUTES = [
  { label: "FSMA 2000", sub: "primary" },
  { label: "FCA Handbook", sub: "COBS · SYSC · DISP" },
  { label: "PRA Rulebook", sub: "" },
  { label: "MLR 2017", sub: "" },
  { label: "PSR 2017", sub: "" },
  { label: "UK MAR", sub: "retained" },
  { label: "RAO 2001", sub: "" },
];

const DIFFERENTIATORS = [
  {
    icon: FiGitBranch,
    title: "Graph-grounded",
    body: "Every answer is anchored to a Neo4j knowledge graph of UK statute, FCA and PRA rules, and statutory instruments — hybrid sparse + dense retrieval with a graph-boost step that surfaces the linked provisions.",
  },
  {
    icon: FiShield,
    title: "Citation-verified",
    body: "Each load-bearing claim is checked against the corpus. Verified citations appear as green chips; anything the verifier can't ground is flagged as caution and shown to you — never silently.",
  },
  {
    icon: FiLock,
    title: "Runs locally",
    body: "FinLaw is built on a local Mistral 7B-Instruct via Ollama and a self-hosted Neo4j. Privileged matter and client data never leave your machine.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Retrieve",
    body: "Hybrid BM25 + dense embeddings narrow the corpus to the most relevant provisions.",
  },
  {
    n: "02",
    title: "Graph-boost",
    body: "Neo4j fulltext search finds connected provisions via citation edges, raising the right rules to the top.",
  },
  {
    n: "03",
    title: "Generate",
    body: "Mistral composes a grounded answer with inline UK short-form citations (FSMA s.19, COBS 4.2.1R, …).",
  },
  {
    n: "04",
    title: "Verify",
    body: "Every citation is checked against the graph. Verified or unverified state is exposed in the sources panel.",
  },
];

function SectionEyebrow({ children }) {
  return (
    <div className="mb-3 inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.18em] text-gold-2">
      <span className="h-px w-6 bg-gold/60" aria-hidden />
      {children}
    </div>
  );
}

function ExampleAnswerCard() {
  return (
    <div className="overflow-hidden rounded-card border border-ivory-3 bg-white shadow-soft">
      {/* card chrome */}
      <div className="flex items-center justify-between border-b border-ivory-3 bg-ivory-2/60 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-ivory-3" />
          <span className="h-2.5 w-2.5 rounded-full bg-ivory-3" />
          <span className="h-2.5 w-2.5 rounded-full bg-ivory-3" />
          <span className="ml-3 font-mono text-[11px] text-slate">
            finlaw.local — chat
          </span>
        </div>
        <span className="font-mono text-[11px] text-slate">mode: finance</span>
      </div>

      <div className="grid gap-0 md:grid-cols-[1fr_300px]">
        {/* answer column */}
        <div className="space-y-4 p-6">
          <div className="flex items-start gap-3">
            <div className="grid h-7 w-7 flex-none place-items-center rounded-full bg-ink text-[11px] font-semibold text-ivory">
              You
            </div>
            <p className="pt-0.5 text-sm text-ink">
              What is the "general prohibition" in UK financial services?
            </p>
          </div>

          <div className="flex items-start gap-3">
            <div className="flex-none">
              <Logo variant="mark" size="sm" />
            </div>
            <div className="prose prose-sm max-w-none text-ink">
              <p>
                Under{" "}
                <span className="cite-chip">FSMA 2000 s.19</span>, no person
                may carry on a regulated activity in the United Kingdom
                unless they are an{" "}
                <em>authorised person</em> or an{" "}
                <em>exempt person</em>. This is the so-called{" "}
                <strong>general prohibition</strong>.
              </p>
              <p>
                Regulated activities are defined by{" "}
                <span className="cite-chip">RAO 2001 art.5</span> and related
                articles. Breach is a criminal offence under{" "}
                <span className="cite-chip">FSMA 2000 s.23</span>, and
                agreements made in contravention are typically unenforceable
                against the customer under{" "}
                <span className="cite-chip">FSMA 2000 s.26</span>.
              </p>
            </div>
          </div>
        </div>

        {/* sources column */}
        <aside className="border-t border-ivory-3 bg-ivory-2/40 p-5 md:border-l md:border-t-0">
          <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate">
            Sources & verification
          </div>
          <ul className="space-y-2 text-xs">
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-verified/15 text-verified">
                <FiCheck size={10} />
              </span>
              <span className="font-mono">FSMA 2000 s.19</span>
              <span className="ml-auto text-slate">verified</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-verified/15 text-verified">
                <FiCheck size={10} />
              </span>
              <span className="font-mono">RAO 2001 art.5</span>
              <span className="ml-auto text-slate">verified</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-verified/15 text-verified">
                <FiCheck size={10} />
              </span>
              <span className="font-mono">FSMA 2000 s.23</span>
              <span className="ml-auto text-slate">verified</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="grid h-4 w-4 place-items-center rounded-full bg-verified/15 text-verified">
                <FiCheck size={10} />
              </span>
              <span className="font-mono">FSMA 2000 s.26</span>
              <span className="ml-auto text-slate">verified</span>
            </li>
          </ul>

          <div className="mt-5 border-t border-ivory-3 pt-3 text-[11px] text-slate">
            Claim trace · 4 claims linked to 4 sources · 0 unverified
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-ivory text-ink">
      <Header />

      {/* HERO */}
      <section className="relative overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(60% 60% at 50% 0%, rgba(184,137,58,0.12) 0%, rgba(247,243,234,0) 60%)",
          }}
        />
        <div className="mx-auto max-w-5xl px-4 pb-16 pt-20 text-center sm:px-6 sm:pt-24">
          <SectionEyebrow>UK financial regulation</SectionEyebrow>
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tightish sm:text-5xl md:text-6xl">
            UK financial regulation,{" "}
            <span className="relative italic text-ink">
              cited.
              <span
                aria-hidden
                className="pointer-events-none absolute -bottom-1 left-0 right-0 h-[3px] bg-gold"
              />
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-pretty text-base text-slate sm:text-lg">
            FinLaw is a graph-grounded research assistant. Ask in plain
            English; receive an answer cited to the FCA Handbook, FSMA, the
            PRA Rulebook, and the supporting statutory instruments — with
            every claim linked back to its source.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              to="/chat"
              className="group inline-flex items-center gap-2 rounded-lg bg-ink px-5 py-3 text-sm font-medium text-ivory shadow-soft transition-colors hover:bg-ink-2"
            >
              Open the chat
              <FiArrowRight
                className="transition-transform group-hover:translate-x-0.5"
                size={16}
              />
            </Link>
            <Link
              to="/eval"
              className="inline-flex items-center gap-2 rounded-lg border border-ivory-3 bg-white px-5 py-3 text-sm font-medium text-ink shadow-soft transition-colors hover:border-gold/40 hover:text-gold-2"
            >
              See the evaluation
            </Link>
          </div>

          <div className="mt-12 flex flex-col items-center gap-3">
            <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-slate">
              Built on
            </span>
            <ul className="flex flex-wrap items-center justify-center gap-2">
              {STATUTES.map((s) => (
                <li key={s.label}>
                  <StatuteBadge label={s.label} sub={s.sub} tone="soft" />
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* DIFFERENTIATORS */}
      <section className="border-t border-ivory-3 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <SectionEyebrow>Why FinLaw</SectionEyebrow>
            <h2 className="font-display text-3xl font-semibold tracking-tightish sm:text-4xl">
              Built for compliance work,{" "}
              <span className="italic">not for vibes.</span>
            </h2>
            <p className="mt-3 text-slate">
              A general-purpose chatbot will gesture at a rule it can't name.
              FinLaw refuses to answer unless the corpus supports it — and
              shows you the receipts when it does.
            </p>
          </div>

          <div className="mt-12 grid gap-5 md:grid-cols-3">
            {DIFFERENTIATORS.map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="group rounded-card border border-ivory-3 bg-ivory/40 p-6 transition-all hover:border-gold/40 hover:bg-white hover:shadow-soft"
              >
                <div className="mb-4 grid h-10 w-10 place-items-center rounded-lg bg-ink text-ivory">
                  <Icon size={18} />
                </div>
                <h3 className="font-display text-xl font-semibold text-ink">
                  {title}
                </h3>
                <p className="mt-2 text-sm text-slate">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* EXAMPLE ANSWER */}
      <section className="bg-ivory">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 md:grid-cols-[1fr_1.2fr] md:items-center">
          <div>
            <SectionEyebrow>See it in context</SectionEyebrow>
            <h2 className="font-display text-3xl font-semibold tracking-tightish sm:text-4xl">
              Every claim, linked to its source.
            </h2>
            <p className="mt-4 text-slate">
              Every answer ships with a <em>Sources &amp; verification</em>{" "}
              panel. Each citation is checked against the knowledge graph
              before you see it — verified citations get a green tick,
              anything the verifier can't ground is flagged in amber.
            </p>
            <p className="mt-3 text-slate">
              You see the claim trace too: which sentence in the answer
              maps to which provision. No more "trust me, the model said so."
            </p>
            <ul className="mt-6 space-y-2 text-sm">
              <li className="flex items-start gap-2">
                <FiCheck className="mt-0.5 flex-none text-verified" size={16} />
                <span>UK short-form citations: FSMA s.19, COBS 4.2.1R, SYSC 1.2.</span>
              </li>
              <li className="flex items-start gap-2">
                <FiCheck className="mt-0.5 flex-none text-verified" size={16} />
                <span>Graph-verified against the indexed corpus on every response.</span>
              </li>
              <li className="flex items-start gap-2">
                <FiCheck className="mt-0.5 flex-none text-verified" size={16} />
                <span>Refusal phrase when retrieval can't ground the question.</span>
              </li>
            </ul>
          </div>
          <ExampleAnswerCard />
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="border-t border-ivory-3 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <SectionEyebrow>How it works</SectionEyebrow>
            <h2 className="font-display text-3xl font-semibold tracking-tightish sm:text-4xl">
              Retrieval, then verification.
            </h2>
            <p className="mt-3 text-slate">
              Four passes between your question and the answer. The graph is
              authoritative; the model is the explainer.
            </p>
          </div>

          <ol className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ n, title, body }) => (
              <li
                key={n}
                className="relative rounded-card border border-ivory-3 bg-ivory/40 p-5"
              >
                <div className="font-mono text-xs text-gold-2">{n}</div>
                <h3 className="mt-2 font-display text-lg font-semibold text-ink">
                  {title}
                </h3>
                <p className="mt-1 text-sm text-slate">{body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* DISSERTATION / TRUST */}
      <section className="bg-ink text-ivory ink-surface">
        <div className="mx-auto grid max-w-6xl gap-12 px-4 py-20 sm:px-6 md:grid-cols-2 md:items-center">
          <div>
            <SectionEyebrow>
              <span className="text-gold">Dissertation-backed</span>
            </SectionEyebrow>
            <h2 className="font-display text-3xl font-semibold tracking-tightish text-ivory sm:text-4xl">
              Not a marketing site dressed as a product.
            </h2>
            <p className="mt-4 text-ivory/80">
              FinLaw started as an MSc dissertation at the University of
              Bradford. Every architectural claim — hybrid retrieval, dense
              embeddings, LangChain, graph verification, RAGAS evaluation —
              is reproducible from this codebase. You can read the evaluation
              report, then run it yourself.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/eval"
                className="inline-flex items-center gap-2 rounded-lg bg-ivory px-5 py-3 text-sm font-medium text-ink hover:bg-white"
              >
                Run the evaluation
                <FiArrowRight size={16} />
              </Link>
              <Link
                to="/chat"
                className="inline-flex items-center gap-2 rounded-lg border border-ivory/25 px-5 py-3 text-sm font-medium text-ivory hover:bg-ivory/10"
              >
                Try a question
              </Link>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-card border border-ivory/10 bg-ink-2 p-5">
              <FiBookOpen className="text-gold" size={20} />
              <div className="mt-3 font-display text-2xl font-semibold">
                7 corpora
              </div>
              <div className="text-sm text-ivory/70">
                FSMA · FCA · PRA · RAO · MLR · PSR · UK MAR
              </div>
            </div>
            <div className="rounded-card border border-ivory/10 bg-ink-2 p-5">
              <FiCpu className="text-gold" size={20} />
              <div className="mt-3 font-display text-2xl font-semibold">
                Local LLM
              </div>
              <div className="text-sm text-ivory/70">
                Mistral 7B-Instruct via Ollama. No third-party calls.
              </div>
            </div>
            <div className="rounded-card border border-ivory/10 bg-ink-2 p-5">
              <FiGitBranch className="text-gold" size={20} />
              <div className="mt-3 font-display text-2xl font-semibold">
                Neo4j graph
              </div>
              <div className="text-sm text-ivory/70">
                Provision-level nodes with 2-hop citation edges.
              </div>
            </div>
            <div className="rounded-card border border-ivory/10 bg-ink-2 p-5">
              <FiShield className="text-gold" size={20} />
              <div className="mt-3 font-display text-2xl font-semibold">
                RAGAS scored
              </div>
              <div className="text-sm text-ivory/70">
                Faithfulness · relevancy · context precision · context recall.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-ivory">
        <div className="mx-auto max-w-4xl px-4 py-20 text-center sm:px-6">
          <h2 className="font-display text-3xl font-semibold tracking-tightish sm:text-4xl">
            Try a question.
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-slate">
            "What is the FSCS deposit protection limit?"  ·  "What standard
            applies to financial promotions?"  ·  "How many days to cancel a
            general insurance policy?"
          </p>
          <div className="mt-7">
            <Link
              to="/chat"
              className="group inline-flex items-center gap-2 rounded-lg bg-ink px-6 py-3.5 text-sm font-medium text-ivory shadow-soft transition-colors hover:bg-ink-2"
            >
              Open the chat
              <FiArrowRight
                className="transition-transform group-hover:translate-x-0.5"
                size={16}
              />
            </Link>
          </div>
        </div>
      </section>

      <DisclaimerBand />
      <Footer />
    </div>
  );
}
