const STEPS = [
  {
    n: "01",
    title: "Watch the contract",
    body: "detector.py pulls OpenAPI, changelogs, PyPI, npm, and GitHub releases from apis.yaml, then diffs them against the last snapshot in .state.",
  },
  {
    n: "02",
    title: "Find the blast radius",
    body: "impact_scanner.py walks the client repo. Endpoint templates become regexes; Python field access is real AST. Every hit gets a confidence score.",
  },
  {
    n: "03",
    title: "Write one patch",
    body: "pipeline.py asks the model only about the complete set of breaking changes, runs the repo’s own tests, and writes fix.patch.",
  },
  {
    n: "04",
    title: "Open a pull request",
    body: "The explanation and check result land on GitHub. Rehearse with python dashboard.py --no-pr if you are not ready to open one.",
  },
]

export function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-6xl px-6 py-20 md:py-28">
      <p className="text-sm font-medium text-muted-foreground">The loop</p>
      <h2 className="font-heading mt-2 max-w-xl text-3xl font-semibold tracking-tight md:text-4xl">
        Same four stages the Python console already runs.
      </h2>
      <ol className="mt-12 grid gap-6 sm:grid-cols-2">
        {STEPS.map((step) => (
          <li key={step.n} className="rounded-xl border bg-card p-6">
            <p className="font-mono text-xs text-muted-foreground">{step.n}</p>
            <h3 className="mt-3 text-lg font-medium">{step.title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.body}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
