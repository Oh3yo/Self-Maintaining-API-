export function SiteFooter() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-6 py-10 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>Detector · impact scanner · fix generator · pull request.</p>
        <p>Mock API on :8000 · Python console on :8001 · this UI on :3000.</p>
      </div>
    </footer>
  )
}
