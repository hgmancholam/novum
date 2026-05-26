/**
 * HomePage — Route: /
 * Owns: useUser, useRunHistory
 * See ui-prototype.md §8.2 (Pages).
 *
 * Renders:
 * - AppShell with HistoryPanel, CenterPanel (QuestionForm + TypeDisclosure), TracePanel (T1 empty)
 */

export default function HomePage() {
  // TODO: Implement with useUser, useRunHistory hooks
  // This is a placeholder for BRD-11 (Frontend Layout)
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
          Novum
        </h1>
        <p className="mt-2 text-[var(--text-secondary)]">
          Research agent that earns its conclusions
        </p>
      </div>
    </div>
  );
}
