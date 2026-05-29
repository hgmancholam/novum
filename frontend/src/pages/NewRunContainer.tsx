/**
 * NewRunContainer — page-level data owner for starting a research (BRD-13 iter 2).
 *
 * Composition:
 *   - `QuestionForm`     — required input + optional context + advanced
 *   - `SuggestionChips`  — first-run onboarding (RF-06, §7.7)
 *
 * Auth gate (BRD-04): anonymous users see the `Sign in` modal first; their
 * draft question is preserved so they don't lose typing.
 *
 * Per `eslint.config.js`, only `pages/` may import data hooks.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";

import {
  QuestionForm,
  type QuestionFormValues,
} from "@/components/organisms";
import { SuggestionChips } from "@/components/molecules";
import { useCreateRun } from "@/hooks/useCreateRun";
import { useLoginModal } from "@/hooks/useLoginModal";
import { useUserStore } from "@/stores/userStore";
import { fadeUp, stagger } from "@/lib/motion";

export function NewRunContainer() {
  const navigate = useNavigate();
  const isAuthenticated = useUserStore((s) => s.isAuthenticated);
  const isVerifying = useUserStore((s) => s.isVerifying);
  const openLogin = useLoginModal((s) => s.open);
  const { create, isPending, error } = useCreateRun();
  const [draft, setDraft] = useState<string>("");

  async function handleSubmit(values: QuestionFormValues) {
    if (!isAuthenticated) {
      // Preserve the draft and open the auth modal.
      setDraft(values.question);
      openLogin();
      return;
    }
    try {
      const run = await create({
        question: values.question,
        user_context: values.userContext,
        output_format: values.outputFormat,
        llm_provider: values.llmProvider,
      });
      void navigate(`/runs/${run.id}`);
    } catch {
      // Error surfaced via `error` prop on the form below.
    }
  }

  const submitError = error !== null ? error.message : null;

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={stagger}
      className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10"
    >
      <motion.header variants={fadeUp} className="text-center">
        <h1 className="text-[2rem] font-semibold leading-tight tracking-tight text-(--text-primary)">
          Ask.{" "}
          <span className="bg-linear-to-r from-(--accent) via-fuchsia-400 to-(--warm) bg-clip-text text-transparent">
            Earn the answer.
          </span>
        </h1>
        <p className="mt-2 text-base text-(--text-secondary)">
          Research agent that earns its conclusions.
        </p>
      </motion.header>

      <motion.div variants={fadeUp}>
        <QuestionForm
          onSubmit={(payload) => {
            void handleSubmit(payload);
          }}
          isSubmitting={isPending || isVerifying}
          submitError={submitError}
          initialQuestion={draft}
        />
      </motion.div>

      <motion.div variants={fadeUp}>
        <SuggestionChips
          onPick={(q) => {
            setDraft(q);
          }}
        />
      </motion.div>
    </motion.div>
  );
}
