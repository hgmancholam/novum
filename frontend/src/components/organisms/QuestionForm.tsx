/**
 * QuestionForm organism — primary onboarding surface (RF-01, RF-06, RF-07).
 *
 * Composition (per ui-prototype.md §7.2):
 *   - <textarea>  required, 10-2000 chars (matches backend `RunCreate`)
 *   - Optional context disclosure (RF-07): textarea, max 1000 chars
 *     counter turns amber at ≥ 900, red at = 1000
 *   - Advanced disclosure (▸/▾):
 *       output_format    Prose | Structured        (default Structured)
 *       confidence_thr.  Low 0.4 | Standard 0.6 | High 0.85 | Custom 0-1
 *   - Submit "Start research" / "Starting…"
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
  confidenceThreshold: number;
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

type ThresholdPreset = "low" | "standard" | "high" | "custom";

const presetValues: Record<Exclude<ThresholdPreset, "custom">, number> = {
  low: 0.4,
  standard: 0.6,
  high: 0.85,
};

const presetLabels: Record<ThresholdPreset, string> = {
  low: "Low (0.4)",
  standard: "Standard (0.6)",
  high: "High (0.85)",
  custom: "Custom\u2026",
};

export function QuestionForm({
  onSubmit,
  isSubmitting = false,
  submitError = null,
  initialQuestion,
  className,
}: QuestionFormProps) {
  const questionId = useId();
  const contextId = useId();
  const formatId = useId();
  const thresholdId = useId();

  const [question, setQuestion] = useState<string>(initialQuestion ?? "");
  const [contextOpen, setContextOpen] = useState<boolean>(false);
  const [userContext, setUserContext] = useState<string>("");
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
  // D-COPY-AND-FORMAT-INLINE: all runs are submitted as `structured`. The
  // user toggles the rendering format inside the answer card, not at
  // submission time.
  const outputFormat: OutputFormat = "structured";
  const [thresholdPreset, setThresholdPreset] =
    useState<ThresholdPreset>("standard");
  const [customThreshold, setCustomThreshold] = useState<number>(0.7);
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

  const threshold =
    thresholdPreset === "custom"
      ? customThreshold
      : presetValues[thresholdPreset];

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
      confidenceThreshold: threshold,
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

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => {
            setAdvancedOpen((v) => !v);
          }}
          aria-expanded={advancedOpen}
          aria-controls={`${formatId}-group`}
          className={cn(
            "inline-flex items-center gap-1 self-start rounded-full",
            "border border-(--glass-border) bg-(--glass-bg) backdrop-blur",
            "px-3 py-1 text-xs text-(--text-secondary)",
            "transition-colors hover:bg-(--glass-hover) hover:text-(--text-primary)",
            "focus-visible:outline-2 focus-visible:outline-(color:--accent) focus-visible:outline-offset-2"
          )}
        >
          {advancedOpen ? "Advanced ▾" : "Advanced ▸"}
        </button>
        {advancedOpen ? (
          <div
            id={`${formatId}-group`}
            className="glass-subtle grid gap-4 rounded-[var(--radius-md)] p-3"
          >
            <fieldset className="flex flex-col gap-1">
              <legend
                id={thresholdId}
                className="text-xs font-medium text-[var(--text-primary)]"
                title="Higher threshold = the agent searches longer and may honest-stop more often."
              >
                Confidence threshold
              </legend>
              <div role="radiogroup" aria-labelledby={thresholdId} className="flex flex-wrap gap-2">
                {(["low", "standard", "high", "custom"] as const).map((p) => (
                  <label
                    key={p}
                    className={cn(
                      "cursor-pointer rounded-[var(--radius-sm)] border px-2 py-1 text-xs transition-colors",
                      thresholdPreset === p
                        ? "border-(--accent) bg-(--accent) text-white"
                        : "glass-subtle text-(--text-secondary) hover:text-(--text-primary)"
                    )}
                  >
                    <input
                      type="radio"
                      name="threshold-preset"
                      value={p}
                      checked={thresholdPreset === p}
                      onChange={() => {
                        setThresholdPreset(p);
                      }}
                      className="sr-only"
                    />
                    {presetLabels[p]}
                  </label>
                ))}
              </div>
              {thresholdPreset === "custom" ? (
                <div className="mt-1 flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={1}
                    step={0.05}
                    value={customThreshold}
                    onChange={(e) => {
                      setCustomThreshold(parseFloat(e.target.value));
                    }}
                    aria-label="Custom confidence threshold (0 to 1)"
                    aria-valuemin={0}
                    aria-valuemax={1}
                    aria-valuenow={customThreshold}
                    className="w-full accent-(--accent)"
                  />
                  <span className="w-8 shrink-0 text-right text-xs tabular-nums text-(--text-secondary)">
                    {customThreshold.toFixed(2)}
                  </span>
                </div>
              ) : null}
            </fieldset>
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
