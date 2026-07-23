/**
 * Blocking "searching…" modal for the Identities tab.
 *
 * A live similarity search is a real round-trip (name/age/sex scored across every
 * accused), so both entry points — the per-row "Find similar" button and the top
 * name search — put up this centered overlay while it runs. The fixed backdrop
 * captures clicks, so the UI is intentionally blocked until results arrive.
 * Returns null when idle. Reduced motion is respected via the stylesheet.
 */
export function SearchingModal({
  show,
  label = "Finding similar people in database — please wait",
}: {
  show: boolean;
  label?: string;
}) {
  if (!show) return null;
  return (
    <div className="searching-overlay" role="alertdialog" aria-busy="true" aria-live="assertive">
      <div className="searching-card">
        <span className="kv-spinner" aria-hidden />
        <span>{label}</span>
      </div>
    </div>
  );
}
