/**
 * HowWeWorkPage — Route: /how-we-work
 *
 * Marketing / storytelling page explaining the Novum research pipeline.
 * Source of truth for the diagram: docs/understanding-phase/building-the-plan.md §"Recomendación: pipeline en capas".
 *
 * Standalone page (no AppShell). Uses the global background gradient defined in index.css.
 */

import { Link } from "react-router-dom";
import { motion, useReducedMotion, type Variants } from "motion/react";
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleSlash,
  Compass,
  Flag,
  Hand,
  Layers,
  Network,
  Search,
  ShieldCheck,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";
import { Logo } from "@/components/atoms";

// ---------------------------------------------------------------------------
// Motion presets
// ---------------------------------------------------------------------------

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] },
  }),
};

const stagger: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HowWeWorkPage() {
  return (
    <div className="relative min-h-dvh w-full overflow-x-hidden text-(--text-primary)">
      <BackgroundOrbs />
      <TopNav />

      <main className="relative z-10 mx-auto w-full max-w-6xl px-6 pt-12 pb-24 sm:px-8">
        <Hero />
        <ProblemStatement />
        <PipelineDiagram />
        <RouteCards />
        <AnatomyOfARun />
        <StopReasons />
        <StrategyTable />
        <CostSavings />
        <ClosingCTA />
      </main>

      <Footer />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Decorative background
// ---------------------------------------------------------------------------

function BackgroundOrbs() {
  const reduce = useReducedMotion();
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
      <motion.div
        className="absolute -top-40 left-1/2 h-160 w-160 -translate-x-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(99,102,241,0.28), transparent 70%)",
          filter: "blur(20px)",
        }}
        animate={reduce ? {} : { y: [0, 18, 0] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute top-1/3 -right-32 h-105 w-105 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(168,85,247,0.18), transparent 70%)",
          filter: "blur(24px)",
        }}
        animate={reduce ? {} : { y: [0, -22, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 left-0 h-95 w-95 rounded-full"
        style={{
          background:
            "radial-gradient(closest-side, rgba(251,191,36,0.10), transparent 70%)",
          filter: "blur(28px)",
        }}
        animate={reduce ? {} : { y: [0, 14, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Top nav (lightweight, page-scoped)
// ---------------------------------------------------------------------------

function TopNav() {
  return (
    <header className="relative z-20 border-b border-(--glass-border) bg-(--bg-secondary)/60 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6 sm:px-8">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-medium text-(--text-primary) transition-opacity hover:opacity-80"
        >
          <Logo size={20} title="" />
          <span>Novum</span>
        </Link>
        <Link
          to="/"
          className="group inline-flex items-center gap-2 rounded-lg border border-(--glass-border) bg-(--glass-bg) px-3 py-1.5 text-xs text-(--text-secondary) transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)"
        >
          <ArrowLeft className="h-3.5 w-3.5 transition-transform group-hover:-translate-x-0.5" />
          Back to Novum
        </Link>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Hero
// ---------------------------------------------------------------------------

function Hero() {
  return (
    <motion.section
      initial="hidden"
      animate="visible"
      variants={stagger}
      className="pt-16 pb-20 text-center sm:pt-24"
    >
      <motion.div
        variants={fadeUp}
        className="mb-6 inline-flex items-center gap-2 rounded-full border border-(--glass-border) bg-(--glass-bg) px-3 py-1 text-xs text-(--text-secondary) backdrop-blur"
      >
        <Sparkles className="h-3.5 w-3.5 text-(--accent)" />
        How Novum thinks
      </motion.div>

      <motion.h1
        variants={fadeUp}
        custom={1}
        className="mx-auto max-w-3xl text-4xl font-semibold tracking-tight text-(--text-primary) sm:text-5xl md:text-6xl"
      >
        Research that knows{" "}
        <span className="bg-linear-to-r from-(--accent) via-fuchsia-400 to-(--warm) bg-clip-text text-transparent">
          when to stop
        </span>
        .
      </motion.h1>

      <motion.p
        variants={fadeUp}
        custom={2}
        className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-(--text-secondary) sm:text-lg"
      >
        Most agents keep digging until they hallucinate. Novum routes every question through a
        layered pipeline that decomposes, verifies and{" "}
        <span className="text-(--text-primary)">honestly stops</span> — answering only when the
        evidence holds up.
      </motion.p>

      <motion.div
        variants={fadeUp}
        custom={3}
        className="mt-10 flex flex-wrap items-center justify-center gap-3"
      >
        <a
          href="#pipeline"
          className="group inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-medium text-white shadow-(--shadow-glow) transition-transform hover:-translate-y-0.5 hover:bg-(--accent-hover)"
        >
          See the pipeline
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </a>
        <a
          href="#strategies"
          className="inline-flex items-center gap-2 rounded-xl border border-(--glass-border) bg-(--glass-bg) px-5 py-2.5 text-sm text-(--text-secondary) transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)"
        >
          Compare strategies
        </a>
      </motion.div>
    </motion.section>
  );
}

// ---------------------------------------------------------------------------
// Problem statement
// ---------------------------------------------------------------------------

function ProblemStatement() {
  const items = [
    {
      icon: Zap,
      title: "One size fits none",
      body: "Running a deep reasoning loop on a trivial lookup wastes tokens; running a shallow lookup on a multi-hop question hallucinates.",
    },
    {
      icon: ShieldCheck,
      title: "Stopping is a feature",
      body: '"I cannot answer" is a first-class success, not a failure. Novum guarantees it with 7 explicit stop reasons.',
    },
    {
      icon: Layers,
      title: "Verification, not vibes",
      body: "Every draft is fact-checked against its own evidence before reaching you. Contradictions trigger a re-draft, not a shrug.",
    },
  ];

  return (
    <motion.section
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, amount: 0.2 }}
      variants={stagger}
      className="grid gap-4 sm:grid-cols-3"
    >
      {items.map((item, i) => (
        <motion.div
          key={item.title}
          variants={fadeUp}
          custom={i}
          className="group rounded-2xl border border-(--glass-border) bg-(--glass-bg) p-5 backdrop-blur-xl transition-colors hover:bg-(--glass-hover)"
        >
          <div className="mb-3 inline-flex h-9 w-9 items-center justify-center rounded-lg bg-(--accent-soft) text-(--accent)">
            <item.icon className="h-4.5 w-4.5" strokeWidth={1.75} />
          </div>
          <div className="text-sm font-medium text-(--text-primary)">{item.title}</div>
          <p className="mt-1.5 text-sm leading-relaxed text-(--text-secondary)">{item.body}</p>
        </motion.div>
      ))}
    </motion.section>
  );
}

// ---------------------------------------------------------------------------
// Pipeline diagram (the centerpiece)
// ---------------------------------------------------------------------------

interface LaneSpec {
  id: "trivial" | "standard" | "deep";
  label: string;
  subtitle: string;
  accent: string;
  glow: string;
  steps: string[];
  icon: typeof Search;
}

const LANES: LaneSpec[] = [
  {
    id: "trivial",
    label: "Trivial",
    subtitle: "One search, one answer",
    accent: "#22d3ee",
    glow: "rgba(34, 211, 238, 0.35)",
    steps: ["Direct search", "Answer"],
    icon: Search,
  },
  {
    id: "standard",
    label: "Standard",
    subtitle: "Decompose → search × N → CoVe",
    accent: "#6366f1",
    glow: "rgba(99, 102, 241, 0.42)",
    steps: ["Decompose", "Parallel search", "Analyze", "Synthesize"],
    icon: Network,
  },
  {
    id: "deep",
    label: "Deep",
    subtitle: "Abductive + ReAct + CoVe",
    accent: "#a855f7",
    glow: "rgba(168, 85, 247, 0.40)",
    steps: ["Hypotheses", "Reason→Act→Obs", "Iterate"],
    icon: Compass,
  },
];

function PipelineDiagram() {
  return (
    <section id="pipeline" className="mt-28 scroll-mt-20">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
        variants={stagger}
        className="mb-10 text-center"
      >
        <motion.div
          variants={fadeUp}
          className="mb-3 inline-flex items-center gap-2 rounded-full border border-(--glass-border) bg-(--glass-bg) px-3 py-1 text-xs text-(--text-secondary)"
        >
          <Workflow className="h-3.5 w-3.5 text-(--accent)" />
          The pipeline
        </motion.div>
        <motion.h2
          variants={fadeUp}
          custom={1}
          className="text-3xl font-semibold tracking-tight sm:text-4xl"
        >
          Three lanes, one honest answer
        </motion.h2>
        <motion.p
          variants={fadeUp}
          custom={2}
          className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed text-(--text-secondary) sm:text-base"
        >
          A lightweight router classifies every question into the cheapest strategy that can
          honestly answer it. Standard and deep lanes converge on a verification step that
          re-checks the draft against evidence.
        </motion.p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.15 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className="relative overflow-hidden rounded-3xl border border-(--glass-border) bg-(--bg-secondary)/40 p-6 backdrop-blur-xl sm:p-10"
      >
        <DiagramSVG />
      </motion.div>
    </section>
  );
}

function DiagramSVG() {
  // Coordinates chosen to fit a 1200x520 viewBox cleanly.
  // Layout:
  //   x=80    Question
  //   x=320   Self-Ask router
  //   x=620   Trivial / Standard / Deep nodes (stacked vertically)
  //   x=900   CoVe (joins standard + deep)
  //   x=1120  Output

  return (
    <svg
      viewBox="0 0 1200 520"
      className="block h-auto w-full"
      role="img"
      aria-label="Novum pipeline: Self-Ask router branches to trivial, standard and deep lanes; standard and deep converge on Chain-of-Verification before the verified output."
    >
      <defs>
        <linearGradient id="grad-trivial" x1="0" x2="1">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.25" />
        </linearGradient>
        <linearGradient id="grad-standard" x1="0" x2="1">
          <stop offset="0%" stopColor="#6366f1" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#6366f1" stopOpacity="0.25" />
        </linearGradient>
        <linearGradient id="grad-deep" x1="0" x2="1">
          <stop offset="0%" stopColor="#a855f7" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#a855f7" stopOpacity="0.25" />
        </linearGradient>
        <linearGradient id="grad-final" x1="0" x2="1">
          <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.7" />
        </linearGradient>
        <filter id="soft-glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Connecting paths */}
      <g fill="none" strokeWidth="2">
        {/* Question → Router */}
        <AnimatedPath d="M 180 260 C 230 260, 250 260, 300 260" stroke="rgba(203,213,225,0.55)" />
        {/* Router → Trivial */}
        <AnimatedPath d="M 440 260 C 510 260, 540 130, 600 130" stroke="url(#grad-trivial)" delay={0.2} />
        {/* Router → Standard */}
        <AnimatedPath d="M 440 260 C 520 260, 540 260, 600 260" stroke="url(#grad-standard)" delay={0.35} />
        {/* Router → Deep */}
        <AnimatedPath d="M 440 260 C 510 260, 540 390, 600 390" stroke="url(#grad-deep)" delay={0.5} />
        {/* Trivial → Output (skip CoVe) */}
        <AnimatedPath
          d="M 770 130 C 880 130, 980 260, 1080 260"
          stroke="url(#grad-trivial)"
          delay={0.65}
          dashed
        />
        {/* Standard → CoVe */}
        <AnimatedPath d="M 770 260 C 830 260, 850 260, 900 260" stroke="url(#grad-standard)" delay={0.65} />
        {/* Deep → CoVe */}
        <AnimatedPath d="M 770 390 C 830 390, 860 260, 900 260" stroke="url(#grad-deep)" delay={0.75} />
        {/* CoVe → Output */}
        <AnimatedPath d="M 1020 260 C 1050 260, 1060 260, 1080 260" stroke="url(#grad-final)" delay={0.9} />
      </g>

      {/* Nodes */}
      <DiagramNode x={80} y={230} w={100} h={60} label="Question" sublabel="User" />
      <DiagramNode
        x={300}
        y={220}
        w={140}
        h={80}
        label="Self-Ask"
        sublabel="Router"
        accent="#6366f1"
        glow
      />

      <DiagramNode
        x={600}
        y={100}
        w={170}
        h={60}
        label="Trivial"
        sublabel="Direct search"
        accent="#22d3ee"
      />
      <DiagramNode
        x={600}
        y={230}
        w={170}
        h={60}
        label="Standard"
        sublabel="Decompose × N"
        accent="#6366f1"
      />
      <DiagramNode
        x={600}
        y={360}
        w={170}
        h={60}
        label="Deep"
        sublabel="ReAct loop"
        accent="#a855f7"
      />

      <DiagramNode
        x={900}
        y={230}
        w={120}
        h={60}
        label="CoVe"
        sublabel="Verify draft"
        accent="#fbbf24"
        glow
      />

      <DiagramNode
        x={1080}
        y={230}
        w={100}
        h={60}
        label="Output"
        sublabel="Verified"
        accent="#10b981"
      />
    </svg>
  );
}

interface AnimatedPathProps {
  d: string;
  stroke: string;
  delay?: number;
  dashed?: boolean;
}

function AnimatedPath({ d, stroke, delay = 0, dashed = false }: AnimatedPathProps) {
  const reduce = useReducedMotion();
  return (
    <motion.path
      d={d}
      stroke={stroke}
      strokeLinecap="round"
      strokeDasharray={dashed && !reduce ? "6 8" : undefined}
      initial={reduce ? { pathLength: 1, opacity: 1 } : { pathLength: 0, opacity: 0 }}
      whileInView={{ pathLength: 1, opacity: 1 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ pathLength: { duration: 1.1, delay, ease: [0.16, 1, 0.3, 1] }, opacity: { duration: 0.3, delay } }}
    />
  );
}

interface DiagramNodeProps {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  sublabel: string;
  accent?: string;
  glow?: boolean;
}

function DiagramNode({
  x,
  y,
  w,
  h,
  label,
  sublabel,
  accent = "#cbd5e1",
  glow = false,
}: DiagramNodeProps) {
  return (
    <motion.g
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
    >
      {glow ? (
        <rect
          x={x - 4}
          y={y - 4}
          width={w + 8}
          height={h + 8}
          rx={16}
          fill={accent}
          opacity={0.18}
          filter="url(#soft-glow)"
        />
      ) : null}
      <rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={14}
        fill="rgba(17, 24, 39, 0.85)"
        stroke={accent}
        strokeOpacity={0.55}
        strokeWidth={1.25}
      />
      <text
        x={x + w / 2}
        y={y + h / 2 - 4}
        textAnchor="middle"
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="14"
        fontWeight={600}
        fill="#f8fafc"
      >
        {label}
      </text>
      <text
        x={x + w / 2}
        y={y + h / 2 + 14}
        textAnchor="middle"
        fontFamily="Inter, system-ui, sans-serif"
        fontSize="11"
        fill="#94a3b8"
      >
        {sublabel}
      </text>
    </motion.g>
  );
}

// ---------------------------------------------------------------------------
// Route cards (lanes explained in prose)
// ---------------------------------------------------------------------------

function RouteCards() {
  return (
    <section className="mt-24">
      <motion.h2
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center text-2xl font-semibold tracking-tight sm:text-3xl"
      >
        Each lane, explained
      </motion.h2>

      <div className="grid gap-5 md:grid-cols-3">
        {LANES.map((lane, i) => (
          <motion.article
            key={lane.id}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ duration: 0.55, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="group relative overflow-hidden rounded-2xl border border-(--glass-border) bg-(--glass-bg) p-6 backdrop-blur-xl transition-colors hover:bg-(--glass-hover)"
          >
            <div
              className="pointer-events-none absolute -top-20 -right-20 h-48 w-48 rounded-full opacity-0 blur-3xl transition-opacity group-hover:opacity-100"
              style={{ background: lane.glow }}
            />
            <div
              className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl"
              style={{
                background: `color-mix(in srgb, ${lane.accent} 18%, transparent)`,
                color: lane.accent,
              }}
            >
              <lane.icon className="h-5 w-5" strokeWidth={1.75} />
            </div>
            <h3 className="text-lg font-semibold text-(--text-primary)">{lane.label}</h3>
            <p className="mt-1 text-sm text-(--text-secondary)">{lane.subtitle}</p>

            <ol className="mt-5 space-y-2">
              {lane.steps.map((step, idx) => (
                <li
                  key={step}
                  className="flex items-center gap-3 text-sm text-(--text-secondary)"
                >
                  <span
                    className="inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold"
                    style={{
                      background: `color-mix(in srgb, ${lane.accent} 16%, transparent)`,
                      color: lane.accent,
                    }}
                  >
                    {idx + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </motion.article>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Strategy comparison table
// ---------------------------------------------------------------------------

interface Strategy {
  name: string;
  effectiveness: number;
  cost: "Low" | "Medium" | "Medium+" | "High" | "Very high";
  hallucination: "Very low" | "Low" | "Medium-low" | "Medium";
  highlight?: boolean;
  note: string;
}

const STRATEGIES: Strategy[] = [
  { name: "Decomposition (pure)", effectiveness: 65, cost: "Low", hallucination: "Medium", note: "Structured queries, no verification" },
  { name: "Self-Ask", effectiveness: 70, cost: "Low", hallucination: "Medium", note: "Query router / classifier" },
  { name: "Abductive Hypothesis", effectiveness: 78, cost: "Medium", hallucination: "Medium-low", note: "Exploratory or ambiguous" },
  { name: "ReAct", effectiveness: 82, cost: "Medium", hallucination: "Low", note: "Adaptive engine for deep lane" },
  { name: "Decomp + Retrieval + CoVe", effectiveness: 87, cost: "Medium", hallucination: "Low", highlight: true, note: "Novum's standard lane" },
  { name: "Debate / Multi-agent", effectiveness: 88, cost: "Very high", hallucination: "Very low", note: "Multi-perspective analysis" },
  { name: "Tree-of-Thoughts", effectiveness: 85, cost: "High", hallucination: "Low", note: "Competing hypotheses" },
  { name: "Chain-of-Verification", effectiveness: 90, cost: "Medium+", hallucination: "Very low", note: "Final fact-check on every draft" },
];

function StrategyTable() {
  return (
    <section id="strategies" className="mt-24 scroll-mt-20">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
        className="mb-8 text-center"
      >
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          The trade-off space
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-(--text-secondary) sm:text-base">
          Nobody wins on every axis. We combine the best of each.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.15 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="overflow-hidden rounded-2xl border border-(--glass-border) bg-(--bg-secondary)/40 backdrop-blur-xl"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-(--glass-border) text-xs uppercase tracking-wider text-(--text-muted)">
              <tr>
                <th className="px-5 py-3 font-medium">Strategy</th>
                <th className="px-5 py-3 font-medium">Effectiveness</th>
                <th className="px-5 py-3 font-medium">LLM cost</th>
                <th className="px-5 py-3 font-medium">Hallucination</th>
                <th className="hidden px-5 py-3 font-medium md:table-cell">Best for</th>
              </tr>
            </thead>
            <tbody>
              {STRATEGIES.map((s) => (
                <tr
                  key={s.name}
                  className={
                    s.highlight
                      ? "border-t border-(--glass-border) bg-(--accent-soft)/40"
                      : "border-t border-(--glass-border) transition-colors hover:bg-(--glass-hover)"
                  }
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-2">
                      {s.highlight ? (
                        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-(--accent) shadow-[0_0_8px_var(--accent-glow)]" />
                      ) : null}
                      <span
                        className={
                          s.highlight
                            ? "font-medium text-(--text-primary)"
                            : "text-(--text-secondary)"
                        }
                      >
                        {s.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-5 py-3.5">
                    <EffectivenessBar value={s.effectiveness} highlight={s.highlight ?? false} />
                  </td>
                  <td className="px-5 py-3.5 text-(--text-secondary)">{s.cost}</td>
                  <td className="px-5 py-3.5 text-(--text-secondary)">{s.hallucination}</td>
                  <td className="hidden px-5 py-3.5 text-(--text-muted) md:table-cell">
                    {s.note}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </section>
  );
}

function EffectivenessBar({ value, highlight }: { value: number; highlight: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-(--glass-border) sm:w-32">
        <motion.div
          className="h-full rounded-full"
          style={{
            background: highlight
              ? "linear-gradient(90deg, var(--accent), var(--warm))"
              : "rgba(203, 213, 225, 0.55)",
          }}
          initial={{ width: 0 }}
          whileInView={{ width: `${value}%` }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
      <span className="text-xs tabular-nums text-(--text-secondary)">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cost savings teaser
// ---------------------------------------------------------------------------

function CostSavings() {
  const dist = [
    { label: "Trivial", value: 50, color: "#22d3ee" },
    { label: "Standard", value: 35, color: "#6366f1" },
    { label: "Deep", value: 15, color: "#a855f7" },
  ];

  return (
    <section className="mt-24">
      <div className="grid items-center gap-10 md:grid-cols-2">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-(--glass-border) bg-(--glass-bg) px-3 py-1 text-xs text-(--text-secondary)">
            <Zap className="h-3.5 w-3.5 text-(--warm)" />
            Routing pays for itself
          </div>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            ~62% fewer LLM calls vs. one-pipeline-fits-all
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-(--text-secondary) sm:text-base">
            Most production traffic is trivial — definitions, dates, lookups. By routing those to a
            single search instead of a full ReAct + verification loop, the average query costs a
            fraction of the worst case while the quality on hard questions stays uncompromised.
          </p>
          <div className="mt-6 grid grid-cols-3 gap-3">
            <Metric label="Avg. cost" value="0.38×" tone="accent" />
            <Metric label="Read determinism" value="100%" />
            <Metric label="Stop reasons" value="7" tone="warm" />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="relative rounded-3xl border border-(--glass-border) bg-(--bg-secondary)/40 p-8 backdrop-blur-xl"
        >
          <h3 className="text-sm font-medium text-(--text-secondary)">
            Typical traffic distribution
          </h3>
          <div className="mt-6 space-y-5">
            {dist.map((d) => (
              <div key={d.label}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="text-(--text-primary)">{d.label}</span>
                  <span className="tabular-nums text-(--text-secondary)">{d.value}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-(--glass-border)">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: d.color, boxShadow: `0 0 12px ${d.color}66` }}
                    initial={{ width: 0 }}
                    whileInView={{ width: `${d.value}%` }}
                    viewport={{ once: true, amount: 0.5 }}
                    transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
              </div>
            ))}
          </div>
          <p className="mt-6 text-xs text-(--text-muted)">
            Based on the cost model in <code className="text-(--text-secondary)">building-the-plan.md</code>.
          </p>
        </motion.div>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "accent" | "warm";
}) {
  const color =
    tone === "accent" ? "var(--accent)" : tone === "warm" ? "var(--warm)" : "var(--text-primary)";
  return (
    <div className="rounded-xl border border-(--glass-border) bg-(--glass-bg) p-3 backdrop-blur">
      <div className="text-xl font-semibold tabular-nums" style={{ color }}>
        {value}
      </div>
      <div className="mt-0.5 text-[11px] uppercase tracking-wider text-(--text-muted)">{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Anatomy of a run (simplified trace example)
// ---------------------------------------------------------------------------

interface TraceStep {
  kind: "plan" | "search" | "evidence" | "judge" | "answer";
  title: string;
  detail: string;
  accent: string;
}

const SAMPLE_TRACE: TraceStep[] = [
  {
    kind: "plan",
    title: "Plan",
    detail: "Decompose into 3 sub-claims: inflation 2024 · methodology · revisions.",
    accent: "var(--accent)",
  },
  {
    kind: "search",
    title: "Search · sub-claim 1",
    detail: "Tavily(advanced) → 5 sources from DANE and Banco de la República.",
    accent: "#22d3ee",
  },
  {
    kind: "evidence",
    title: "Evidence",
    detail: "Two independent primary sources agree on 5.20%. Confidence: 0.86.",
    accent: "#22d3ee",
  },
  {
    kind: "search",
    title: "Search · sub-claim 2",
    detail: "Wikipedia + Tavily → CPI methodology confirmed (basket weights 2020).",
    accent: "#22d3ee",
  },
  {
    kind: "judge",
    title: "Judge",
    detail: "All sub-claims covered, no contradictions, sources heterogeneous.",
    accent: "var(--warm)",
  },
  {
    kind: "answer",
    title: "Verified output",
    detail: "stop_reason = judge_confirmed · final_confidence = 0.86.",
    accent: "var(--semantic-success)",
  },
];

function AnatomyOfARun() {
  return (
    <section className="mt-28">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
        className="mb-10 text-center"
      >
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-(--glass-border) bg-(--glass-bg) px-3 py-1 text-xs text-(--text-secondary)">
          <Sparkles className="h-3.5 w-3.5 text-(--accent)" />
          Anatomy of a run
        </div>
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Every step is logged. Every claim has a source.
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-(--text-secondary) sm:text-base">
          Below is what Novum's trace looks like for a standard-lane question.
          Re-opening the run replays the exact same steps — read determinism is a guarantee, not best-effort.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.15 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="relative overflow-hidden rounded-2xl border border-(--glass-border) bg-(--bg-secondary)/40 p-6 backdrop-blur-xl sm:p-8"
      >
        <div className="mb-6 flex items-center gap-2 border-b border-(--glass-border) pb-4">
          <span className="inline-flex h-2 w-2 rounded-full bg-(--semantic-success) shadow-[0_0_8px_rgba(16,185,129,0.6)]" />
          <span className="text-sm text-(--text-secondary)">
            run_id ·{" "}
            <span className="font-mono text-(--text-primary)">novum-7c4e…</span>
          </span>
          <span className="ml-auto text-xs text-(--text-muted)">
            Q: "What was Colombia's inflation in 2024?"
          </span>
        </div>

        <ol className="relative space-y-5 pl-6">
          <span
            aria-hidden
            className="absolute top-1 bottom-1 left-1.75 w-px bg-linear-to-b from-(--glass-border) via-(--glass-border) to-transparent"
          />
          {SAMPLE_TRACE.map((step, i) => (
            <motion.li
              key={step.title}
              initial={{ opacity: 0, x: -12 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{
                duration: 0.4,
                delay: i * 0.08,
                ease: [0.16, 1, 0.3, 1],
              }}
              className="relative"
            >
              <span
                aria-hidden
                className="absolute top-1.5 -left-6 inline-flex h-3.5 w-3.5 items-center justify-center rounded-full"
                style={{
                  background: `color-mix(in srgb, ${step.accent} 30%, var(--bg-primary))`,
                  boxShadow: `0 0 0 3px var(--bg-primary), 0 0 10px ${step.accent}`,
                }}
              />
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span
                  className="text-xs font-semibold uppercase tracking-wider"
                  style={{ color: step.accent }}
                >
                  {step.title}
                </span>
                <span className="text-sm text-(--text-secondary)">{step.detail}</span>
              </div>
            </motion.li>
          ))}
        </ol>
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// What stops a run (RF-02: stop_reason enum)
// ---------------------------------------------------------------------------

interface StopReasonItem {
  reason: string;
  label: string;
  body: string;
  tone: "success" | "warning" | "danger" | "neutral";
  Icon: typeof CheckCircle2;
  positive?: boolean;
}

const STOP_REASONS: StopReasonItem[] = [
  {
    reason: "judge_confirmed",
    label: "Confirmed",
    body: "The judge agrees: claims are covered, sources are heterogeneous and the answer holds.",
    tone: "success",
    Icon: CheckCircle2,
    positive: true,
  },
  {
    reason: "honest_unanswerable",
    label: "Unanswerable",
    body: "The evidence is simply not there — Novum says so instead of guessing.",
    tone: "neutral",
    Icon: CircleSlash,
  },
  {
    reason: "honest_contradiction",
    label: "Contradiction",
    body: "Sources disagree and the conflict cannot be resolved. The disagreement is reported as-is.",
    tone: "warning",
    Icon: AlertTriangle,
  },
  {
    reason: "honest_ambiguous",
    label: "Ambiguous",
    body: "Multiple plausible interpretations of the question; the run surfaces them rather than picking blindly.",
    tone: "warning",
    Icon: Flag,
  },
  {
    reason: "stopped_by_budget",
    label: "Budget reached",
    body: "Token, time or tool-call ceiling hit. The partial trace is preserved.",
    tone: "neutral",
    Icon: Layers,
  },
  {
    reason: "user_cancelled",
    label: "Cancelled",
    body: "You stopped the run. Everything captured so far stays on disk.",
    tone: "neutral",
    Icon: Hand,
  },
  {
    reason: "errored",
    label: "Errored",
    body: "Infrastructure failure (upstream API, network). Logged with the failing step.",
    tone: "danger",
    Icon: Ban,
  },
];

const TONE: Record<StopReasonItem["tone"], { fg: string; bg: string }> = {
  success: { fg: "var(--semantic-success)", bg: "rgba(16, 185, 129, 0.14)" },
  warning: { fg: "var(--semantic-warning)", bg: "rgba(245, 158, 11, 0.14)" },
  danger: { fg: "var(--semantic-danger)", bg: "rgba(239, 68, 68, 0.14)" },
  neutral: { fg: "var(--text-secondary)", bg: "var(--glass-bg)" },
};

function StopReasons() {
  return (
    <section className="mt-28">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
        className="mb-10 text-center"
      >
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-(--glass-border) bg-(--glass-bg) px-3 py-1 text-xs text-(--text-secondary)">
          <ShieldCheck className="h-3.5 w-3.5 text-(--warm)" />
          Honest stops
        </div>
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Seven ways a run can end. None of them is a lie.
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-(--text-secondary) sm:text-base">
          Every terminal state maps to one of seven explicit{" "}
          <code className="rounded bg-(--glass-bg) px-1.5 py-0.5 font-mono text-xs text-(--text-primary)">
            stop_reason
          </code>{" "}
          values. "Cannot answer" is a first-class success.
        </p>
      </motion.div>

      <motion.ul
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.1 }}
        variants={stagger}
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
      >
        {STOP_REASONS.map((s, i) => {
          const tone = TONE[s.tone];
          return (
            <motion.li
              key={s.reason}
              variants={fadeUp}
              custom={i}
              className={
                s.positive
                  ? "group rounded-2xl border border-(--glass-border) bg-linear-to-br from-(--accent-soft)/40 to-transparent p-5 backdrop-blur-xl"
                  : "group rounded-2xl border border-(--glass-border) bg-(--glass-bg) p-5 backdrop-blur-xl transition-colors hover:bg-(--glass-hover)"
              }
            >
              <div className="flex items-start gap-3">
                <span
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                  style={{ background: tone.bg, color: tone.fg }}
                >
                  <s.Icon className="h-4.5 w-4.5" strokeWidth={1.75} />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <h3 className="text-sm font-semibold text-(--text-primary)">
                      {s.label}
                    </h3>
                    <code className="truncate font-mono text-[11px] text-(--text-muted)">
                      {s.reason}
                    </code>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-(--text-secondary)">
                    {s.body}
                  </p>
                </div>
              </div>
            </motion.li>
          );
        })}
      </motion.ul>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Closing CTA
// ---------------------------------------------------------------------------

function ClosingCTA() {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="relative mt-28 overflow-hidden rounded-3xl border border-(--glass-border) bg-linear-to-br from-(--accent-soft) via-transparent to-(--warm-soft) p-10 text-center backdrop-blur-xl sm:p-14"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 0%, rgba(99,102,241,0.35), transparent 70%)",
        }}
      />
      <h2 className="relative text-2xl font-semibold tracking-tight sm:text-3xl">
        Ready to see it in action?
      </h2>
      <p className="relative mx-auto mt-3 max-w-xl text-sm text-(--text-secondary) sm:text-base">
        Ask Novum a hard question. Watch it route, search, verify — and stop when it should.
      </p>
      <div className="relative mt-7 flex flex-wrap items-center justify-center gap-3">
        <Link
          to="/"
          className="group inline-flex items-center gap-2 rounded-xl bg-(--accent) px-5 py-2.5 text-sm font-medium text-white shadow-(--shadow-glow) transition-transform hover:-translate-y-0.5 hover:bg-(--accent-hover)"
        >
          Open Novum
          <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </div>
    </motion.section>
  );
}

// ---------------------------------------------------------------------------
// Footer
// ---------------------------------------------------------------------------

function Footer() {
  return (
    <footer className="relative z-10 border-t border-(--glass-border) bg-(--bg-secondary)/40 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-6 text-xs text-(--text-muted) sm:flex-row sm:px-8">
        <div className="flex items-center gap-2">
          <Logo size={16} title="" />
          <span>Novum — single-server research agent</span>
        </div>
        <div>Pipeline doc: <span className="text-(--text-secondary)">building-the-plan.md</span></div>
      </div>
    </footer>
  );
}
