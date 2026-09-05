/** Placeholder for pages not yet built out by a Phase 2 workstream --
 * never wired to fake data, just an honest "not built yet" so the route
 * tree is fully navigable while each page is filled in. */
export function ComingSoonPage({ title }: { title: string }) {
  return (
    <main className="mx-auto flex max-w-lg flex-col items-center gap-2 px-4 py-24 text-center">
      <h1 className="text-lg font-semibold">{title}</h1>
      <p className="support-text">This section is being built.</p>
    </main>
  )
}
