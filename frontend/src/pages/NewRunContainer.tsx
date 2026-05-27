/**
 * NewRunContainer — page-level data owner for starting a research (BRD-13 iter 2).
 *
 * Composition:
 *   - `QuestionForm`     — required input + optional context + advanced
 *   - `SuggestionChips`  — first-run onboarding (RF-06, §7.7)
 *   - `TypeDisclosure`   — supported/rejected types (RF-06, §7.3)
 *
 * Auth gate (BRD-04): anonymous users see the `Sign in` modal first; their
 * draft question is preserved so they don't lose typing.
 *
 * Per `eslint.config.js`, only `pages/` may import data hooks.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  QuestionForm,
  type QuestionFormValues,
} from "@/components/organisms";
import { SuggestionChips, TypeDisclosure } from "@/components/molecules";
import { useCreateRun } from "@/hooks/useCreateRun";
import { useLoginModal } from "@/hooks/useLoginModal";
import { useUserStore } from "@/stores/userStore";

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
        confidence_threshold: values.confidenceThreshold,
      });
      void navigate(`/runs/${run.id}`);
    } catch {
      // Error surfaced via `error` prop on the form below.
    }
  }

  const submitError = error !== null ? error.message : null;

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="text-center">
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">
          Novum
        </h1>
        <p className="mt-1 text-base text-[var(--text-secondary)]">
          Research agent that earns its conclusions.
        </p>
      </header>

      <QuestionForm
        onSubmit={(payload) => {
          void handleSubmit(payload);
        }}
        isSubmitting={isPending || isVerifying}
        submitError={submitError}
        initialQuestion={draft}
      />

      <SuggestionChips
        onPick={(q) => {
          setDraft(q);
        }}
      />

      <TypeDisclosure />
    </div>
  );
}
