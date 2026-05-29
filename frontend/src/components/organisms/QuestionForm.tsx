/**
 * QuestionForm organism — primary onboarding surface (RF-01, RF-06, RF-07).
 *
 * Composition (per ui-prototype.md §7.2):
 *   - <textarea>  required, 10-2000 chars (matches backend `RunCreate`)
 *   - Optional context disclosure (RF-07): textarea, max 1000 chars
 *     counter turns amber at ≥ 900, red at = 1000
 *   - Submit "Start research" / "Starting…"
 *
 * The confidence threshold is no longer exposed in the form — the backend
 * applies its server-side default.
 *
 * Pure presentational: the page-level container (`NewRunContainer`) handles
 * auth gate + mutation + navigation. Per `eslint.config.js` organisms must
 * not import hooks that fetch data.
 */

import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import { Button, ProviderSelect } from "@/components/atoms";
import { cn } from "@/lib/cn";
import {
  DEFAULT_PROVIDER,
  setStoredProvider,
  type LlmProviderName,
} from "@/lib/providers";
import type { OutputFormat } from "@/types/events";

const QUESTION_MIN = 10;
const QUESTION_MAX = 2000;
const CONTEXT_MAX = 1000;
const CONTEXT_AMBER_AT = 900;

export interface QuestionFormValues {
  question: string;
  userContext: string | null;
  outputFormat: OutputFormat;
  llmProvider: LlmProviderName;
}

export interface QuestionFormProps {
  onSubmit: (values: QuestionFormValues) => void;
  isSubmitting?: boolean | undefined;
  submitError?: string | null | undefined;
  /** Controlled initial question — used by SuggestionChips. */
  initialQuestion?: string | undefined;
  className?: string | undefined;
}

export function QuestionForm({
  onSubmit,
  isSubmitting = false,
  submitError = null,
  initialQuestion,
  className,
}: QuestionFormProps) {
  const questionId = useId();
  const contextId = useId();

  const [question, setQuestion] = useState<string>(initialQuestion ?? "");
  const [contextOpen, setContextOpen] = useState<boolean>(false);
  const [userContext, setUserContext] = useState<string>("");
  // D-COPY-AND-FORMAT-INLINE: all runs are submitted as `structured`. The
  // user toggles the rendering format inside the answer card, not at
  // submission time.
  const outputFormat: OutputFormat = "structured";
  const [localError, setLocalError] = useState<string | null>(null);
  // Provider selection — every new question form starts on the project
  // default (Anthropic Claude). The user can still switch per-run; the
  // selection is persisted to localStorage but no longer rehydrated so
  // each new question lands on the recommended model.
  const [llmProvider, setLlmProvider] = useState<LlmProviderName>(
    () => DEFAULT_PROVIDER
  );

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // SuggestionChips picks a question by updating `initialQuestion`. We only
  // overwrite the input when the current value is empty so user typing wins.
  useEffect(() => {
    if (
      initialQuestion !== undefined &&
      initialQuestion !== "" &&
      question === ""
    ) {
      setQuestion(initialQuestion);
    }
    // We deliberately omit `question` from the dep array so typing does
    // not retrigger the sync.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  const trimmedQuestion = question.trim();
  const questionLen = trimmedQuestion.length;
  const tooShort = questionLen > 0 && questionLen < QUESTION_MIN;
  const tooLong = questionLen > QUESTION_MAX;
  const contextLen = userContext.length;
  const contextOver = contextLen > CONTEXT_MAX;

  const canSubmit =
    !isSubmitting &&
    questionLen >= QUESTION_MIN &&
    !tooLong &&
    !contextOver;

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLocalError(null);
    if (questionLen < QUESTION_MIN) {
      setLocalError(
        `Question must be at least ${QUESTION_MIN} characters.`
      );
      textareaRef.current?.focus();
      return;
    }
    if (tooLong) {
      setLocalError(
        `Question must be at most ${QUESTION_MAX} characters.`
      );
      return;
    }
    if (contextOver) {
      setLocalError(`Context must be at most ${CONTEXT_MAX} characters.`);
      return;
    }
    const ctx =
      contextOpen && userContext.trim().length > 0 ? userContext.trim() : null;
    onSubmit({
      question: trimmedQuestion,
      userContext: ctx,
      outputFormat,
      llmProvider,
    });
  }

  const errorMessage = submitError ?? localError;

  const counterColor =
    contextLen >= CONTEXT_MAX
      ? "text-[var(--semantic-danger)]"
      : contextLen >= CONTEXT_AMBER_AT
        ? "text-[var(--semantic-warning)]"
        : "text-[var(--text-muted)]";

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      data-testid="question-form"
      aria-describedby={errorMessage !== null ? `${questionId}-error` : undefined}
      className={cn(
        "glass mx-auto flex w-full max-w-3xl flex-col gap-4",
        "rounded-[var(--radius-lg)] p-6 shadow-(--shadow-md)",
        className
      )}
    >
      <div className="flex flex-col gap-2">
        <label
          htmlFor={questionId}
          className="text-sm font-medium text-[var(--text-primary)]"
        >
          Your question
        </label>
        <textarea
          id={questionId}
          ref={textareaRef}
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
          }}
          placeholder="Ask Novum a question…"
          rows={3}
          maxLength={QUESTION_MAX + 50}
          aria-invalid={tooShort || tooLong || undefined}
          aria-required="true"
          className={cn(
            "min-h-[88px] w-full resize-y rounded-[var(--radius-md)] border",
            "border-(--glass-border) bg-(--bg-tertiary) px-3 py-2",
            "text-base text-(--text-primary)",
            "placeholder:text-(--text-muted)",
            "transition-[border-color,box-shadow] duration-150 ease-out",
            "focus-visible:outline-none focus-visible:border-(--accent)",
            "focus-visible:shadow-[0_0_0_3px_var(--accent-soft)]"
          )}
        />
        <div className="flex items-center justify-between text-xs">
          <span
            className={cn(
              tooLong
                ? "text-[var(--semantic-danger)]"
                : "text-[var(--text-muted)]"
            )}
          >
            {questionLen}/{QUESTION_MAX}
          </span>
          {tooShort ? (
            <span className="text-[var(--semantic-warning)]">
              At least {QUESTION_MIN} characters
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => {
              setContextOpen((v) => !v);
            }}
            aria-expanded={contextOpen}
            aria-controls={contextId}
            className={cn(
              "inline-flex items-center gap-1 rounded-full",
              "border border-(--glass-border) bg-(--glass-bg) backdrop-blur",
              "px-3 py-1 text-xs text-(--text-secondary)",
              "transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)",
              "focus-visible:outline-2 focus-visible:outline-(color:--accent) focus-visible:outline-offset-2"
            )}
          >
            {contextOpen ? "Hide context \u25BE" : "Add context (optional) \u25B8"}
          </button>
          <ProviderSelect
            value={llmProvider}
            onChange={(next) => {
              setLlmProvider(next);
              setStoredProvider(next);
            }}
            disabled={isSubmitting}
          />
        </div>
        {contextOpen ? (
          <div className="flex flex-col gap-1">
            <label
              htmlFor={contextId}
              className="text-xs font-medium text-[var(--text-primary)]"
            >
              Background context (optional)
            </label>
            <textarea
              id={contextId}
              value={userContext}
              onChange={(e) => {
                setUserContext(e.target.value);
              }}
              placeholder="Anything Novum should know up front. Not treated as evidence."
              rows={2}
              maxLength={CONTEXT_MAX + 1}
              aria-invalid={contextOver || undefined}
              className={cn(
                "w-full resize-y rounded-[var(--radius-md)] border",
                "border-(--glass-border) bg-(--bg-tertiary) px-3 py-2",
                "text-sm text-(--text-primary)",
                "placeholder:text-(--text-muted)",
                "transition-[border-color,box-shadow] duration-150 ease-out",
                "focus-visible:outline-none focus-visible:border-(--accent)",
                "focus-visible:shadow-[0_0_0_3px_var(--accent-soft)]"
              )}
            />
            <span className={cn("self-end text-xs tabular-nums", counterColor)}>
              {contextLen}/{CONTEXT_MAX}
            </span>
          </div>
        ) : null}
      </div>

      {errorMessage !== null && errorMessage !== "" ? (
        <p
          id={`${questionId}-error`}
          role="alert"
          className="text-sm text-[var(--semantic-danger)]"
        >
          {errorMessage}
        </p>
      ) : null}

      <div className="flex items-center justify-end gap-2">
        <Button
          type="submit"
          variant="primary"
          size="md"
          disabled={!canSubmit}
          loading={isSubmitting}
          data-testid="submit-question"          title={
            !isSubmitting && questionLen < QUESTION_MIN
              ? "Type a question to start."
              : undefined
          }        >
          {isSubmitting ? "Starting…" : "Start research"}
        </Button>
      </div>
    </form>
  );
}

export const QUESTION_FORM_LIMITS = {
  questionMin: QUESTION_MIN,
  questionMax: QUESTION_MAX,
  contextMax: CONTEXT_MAX,
} as const;
