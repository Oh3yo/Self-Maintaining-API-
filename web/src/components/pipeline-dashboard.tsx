"use client"

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { SAMPLE_BROKEN, type PipelineState } from "@/lib/pipeline"

const COLORS: Record<string, string> = {
  stable: "#dce7dd",
  broken: "#ff4b2b",
  run: "#2358ff",
  ready: "#17744a",
  opened: "#0e4d32",
  fail: "#7a1410",
}

function plan(s: PipelineState) {
  const d = s.detect
  const f = s.fix
  const broken = s.field !== "email"
  const crash = /crashed/.test(s.app)
  const stale = Boolean(d && d.summary.breaking && !broken)
  const D = stale ? null : d
  const F = stale ? null : f
  const fixLabel = s.no_pr ? "Generate Fix" : "Fix And Open Pull Request"
  if (s.busy === "detect")
    return { st: "run", t: "Checking the API…", sub: "Comparing the live spec with the saved baseline." }
  if (s.busy === "fix")
    return {
      st: "run",
      t: "Writing the fix…",
      sub: "Finding the affected code, asking the model, checking the patch.",
    }
  if (D && !D.ok) return { st: "fail", t: "Detector failed.", sub: "See the detector log.", act: "detect" as const, actLabel: "Run Detector Again" }
  if (F && !F.ok) return { st: "fail", t: "The fix failed.", sub: "See the fix log.", act: "fix" as const, actLabel: "Try Again" }
  if (F && F.pr) return { st: "opened", t: "Pull request opened.", sub: "The fix, the explanation and the check result are waiting for review.", link: F.pr }
  if (F && F.patch) return { st: "ready", t: "The fix is ready.", sub: F.checks || "Review the patch below." }
  if (F && F.none) return { st: "stable", t: "Nothing to fix.", sub: "No code in the repo uses what changed." }
  if (D && D.summary.breaking)
    return {
      st: "broken",
      t: "Change detected.",
      sub: `${D.summary.breaking} breaking change${D.summary.breaking === 1 ? "" : "s"} in the API.`,
      act: "fix" as const,
      actLabel: fixLabel,
    }
  if (broken)
    return {
      st: "broken",
      t: "The API changed.",
      sub: crash ? "Your app is crashing. Run the detector to find out why." : "Run the detector to see what changed.",
      act: "detect" as const,
      actLabel: "Run Detector",
    }
  if (stale) return { st: "stable", t: "API restored.", sub: "Reset the demo to start again.", act: "restart" as const, actLabel: "Reset Demo" }
  if (!D) return { st: "stable", t: "Everything works.", sub: "Save the API’s current shape as a baseline first.", act: "detect" as const, actLabel: "Save Baseline" }
  return { st: "stable", t: "Baseline saved.", sub: "Now break the API and watch what happens.", act: "break" as const, actLabel: "Break The API" }
}

function diffLines(patch: string) {
  return patch.split("\n").map((line, i) => {
    const cls = line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")
      ? "text-[#7d8da6]"
      : line.startsWith("+")
        ? "bg-[rgba(46,160,67,.16)] text-[#7ee0a0]"
        : line.startsWith("-")
          ? "bg-[rgba(248,81,73,.16)] text-[#ff8a78]"
          : ""
    return (
      <span key={i} className={`block min-h-[1.4em] ${cls}`}>
        {line || " "}
      </span>
    )
  })
}

export function PipelineDashboard({ compact = false }: { compact?: boolean }) {
  const [state, setState] = useState<PipelineState>(SAMPLE_BROKEN)
  const [preview, setPreview] = useState(true)

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/pipeline/state", { cache: "no-store" })
      const data = (await res.json()) as PipelineState
      if (!data.offline) {
        setPreview(false)
        setState(data)
      }
    } catch {
      /* keep last view */
    }
  }, [])

  useEffect(() => {
    void load()
    const id = setInterval(() => void load(), 1500)
    return () => clearInterval(id)
  }, [load])

  const run = async (name: string) => {
    if (preview) return
    await fetch(`/api/pipeline/do/${name}`, { method: "POST" })
    await load()
  }

  const p = useMemo(() => plan(state), [state])
  const broken = state.field !== "email"
  const crash = /crashed/.test(state.app)
  const off = Boolean(state.busy)
  const ink = p.st === "stable" ? "#11161c" : "#fff"

  return (
    <div className={compact ? "" : "min-h-screen bg-[#f3f4f1]"}>
      <section className="px-6 py-10 md:py-14" style={{ background: COLORS[p.st], color: ink }}>
        <div className="mx-auto max-w-6xl">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm font-semibold">Self-Maintaining API</p>
            {preview ? (
              <Badge variant="secondary" className="bg-black/10 text-inherit">
                Preview data — start python dashboard.py for the live loop
              </Badge>
            ) : null}
            {state.no_pr ? (
              <Badge variant="secondary" className="bg-black/10 text-inherit">
                Rehearsal: no pull requests
              </Badge>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto text-inherit hover:bg-black/10 hover:text-inherit"
              disabled={off || preview}
              onClick={() => void run("restart")}
            >
              Reset Demo
            </Button>
          </div>
          <h1 className="font-heading mt-8 max-w-[16ch] text-4xl font-extrabold tracking-tight md:text-6xl">
            {p.t}
          </h1>
          <div className="mt-8 grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,420px)] md:items-end">
            <div>
              <p className="max-w-[36ch] text-lg leading-7">{p.sub}</p>
              <div className="mt-6">
                {"link" in p && p.link ? (
                  <Button size="lg" className="rounded-full" asChild>
                    <a href={p.link} target="_blank" rel="noreferrer">
                      Open Pull Request
                    </a>
                  </Button>
                ) : "act" in p && p.act ? (
                  <Button size="lg" className="rounded-full" disabled={off || preview} onClick={() => void run(p.act!)}>
                    {p.actLabel}
                  </Button>
                ) : null}
              </div>
            </div>
            <div className="bg-[#11161c] p-5 text-[#d7e0ee]">
              <pre className="font-mono text-sm leading-6 whitespace-pre-wrap">{`GET /v1/users/1
{
  "id": 1,
  "`}<span className={broken ? "bg-[#ff4b2b] px-1 font-bold text-white" : "bg-[#7ee0a0] px-1 font-bold text-[#11161c]"}>{state.field}</span>{`": "tsu@example.com"
}`}</pre>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="secondary" disabled={off || preview || broken} onClick={() => void run("break")}>
                  Break The API
                </Button>
                <Button size="sm" variant="secondary" disabled={off || preview || !broken} onClick={() => void run("reset")}>
                  Restore
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto grid max-w-6xl gap-3 px-6 py-6">
        <Stage title="Your App" status={crash ? "Crashing" : "Working"} tone={crash ? "bad" : "ok"}>
          <pre className="overflow-auto bg-[#11161c] p-4 font-mono text-sm text-[#d7e0ee]">{state.app}</pre>
        </Stage>
        <Stage
          title="Change Detector"
          status={
            state.busy === "detect"
              ? "Running…"
              : !state.detect
                ? "Not run yet"
                : state.detect.summary.breaking
                  ? `${state.detect.summary.breaking} breaking`
                  : "No changes"
          }
          tone={state.busy === "detect" ? "run" : state.detect?.summary.breaking ? "bad" : "ok"}
          action={
            <Button size="sm" variant="outline" disabled={off || preview} onClick={() => void run("detect")}>
              Run Detector
            </Button>
          }
        >
          {state.detect?.changes.length ? (
            <ul className="grid gap-3 text-sm">
              {state.detect.changes.map((c) => (
                <li key={c.location}>
                  <Badge variant={c.severity === "breaking" ? "destructive" : "secondary"}>{c.severity}</Badge>{" "}
                  <code className="font-mono text-xs">{c.location}</code>
                  <p className="mt-1 text-muted-foreground">{c.message}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              Run it once while the API is stable to save a baseline, then again after you break it.
            </p>
          )}
        </Stage>
        <Stage
          title="Fix Generator"
          status={!state.fix ? "Not run yet" : state.fix.pr ? "Patch ready" : "Patch ready"}
          tone={state.fix ? "ok" : ""}
          action={
            <Button size="sm" variant="outline" disabled={off || preview || !state.detect} onClick={() => void run("fix")}>
              {state.no_pr ? "Generate Fix" : "Fix And Open Pull Request"}
            </Button>
          }
        >
          {state.fix ? (
            <div className="grid gap-4 text-sm">
              <div>
                <p className="text-muted-foreground">Upstream change</p>
                {state.fix.changes.map((c) => (
                  <p key={c}>{c}</p>
                ))}
              </div>
              <div>
                <p className="text-muted-foreground">Fix from {state.fix.model}</p>
                <p>{state.fix.summary}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Files</p>
                <code>{state.fix.files}</code>
              </div>
              <pre className="overflow-auto bg-[#11161c] p-4 font-mono text-xs text-[#d7e0ee]">
                {diffLines(state.fix.patch)}
              </pre>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Finds the code that uses the changed API, asks the model for a fix, and checks it before
              opening a pull request.
            </p>
          )}
        </Stage>
        <Stage title="Pull Request" status={state.fix?.pr ? "Opened" : "Waiting"} tone={state.fix?.pr ? "ok" : ""}>
          {state.fix?.pr ? (
            <a className="font-mono text-sm text-blue-700 break-all" href={state.fix.pr} target="_blank" rel="noreferrer">
              {state.fix.pr}
            </a>
          ) : (
            <p className="text-sm text-muted-foreground">
              The fix, an explanation and the check result land here as a pull request for review.
            </p>
          )}
        </Stage>
      </div>
    </div>
  )
}

function Stage({
  title,
  status,
  tone,
  action,
  children,
}: {
  title: string
  status: string
  tone: string
  action?: React.ReactNode
  children: ReactNode
}) {
  const dot =
    tone === "ok" ? "bg-[#17744a]" : tone === "bad" ? "bg-[#d4361d]" : tone === "run" ? "bg-[#2358ff]" : "bg-[#bfc3ba]"
  return (
    <Card className="grid gap-4 bg-[#e7e9e4] py-6 shadow-none ring-0 sm:grid-cols-[220px_minmax(0,1fr)]">
      <CardHeader className="py-0">
        <div className="flex items-start gap-3">
          <span className={`mt-1 size-3.5 rounded-full ${dot}`} />
          <div>
            <CardTitle className="text-xl">{title}</CardTitle>
            <p className="text-sm text-muted-foreground">{status}</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {action}
        {children}
      </CardContent>
    </Card>
  )
}
