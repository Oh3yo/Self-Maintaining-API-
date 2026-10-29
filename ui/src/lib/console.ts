import { useCallback, useEffect, useState } from "react"
import sample from "@/data/sample-run.json"

export type Change = { severity: string; location: string; message: string }
export type Detect = { ok: boolean; out: string; summary: { breaking?: number }; status: string[]; changes: Change[] }
export type Fix = {
  ok: boolean; out: string; none: boolean; changes: string[]; model: string | null; summary: string | null
  files: string | null; checks: string | null; pr: string | null; patch: string
}
export type State = { busy: string | null; field: string; app: string; no_pr: boolean; detect: Detect | null; fix: Fix | null }
export type Tone = "idle" | "ok" | "bad" | "run"
export type Plan = { tone: Tone; title: string; sub: string; act?: [string, string]; link?: string }

const tidy = (t: string | null) => (t ?? "").replace(/`/g, "")
const lastLine = (out: string) => (out.trim().split("\n").filter(Boolean).pop() ?? "").slice(0, 160)
const plural = (n: number) => (n === 1 ? "1 breaking change" : `${n} breaking changes`)

export const isBroken = (s: State) => s.field !== "email"

/** Same decision table as the original dashboard.py page, so the headline always matches the backend. */
export function plan(s: State): Plan {
  const d = s.detect, f = s.fix, broken = isBroken(s), crash = /crashed/.test(s.app)
  const stale = !!d && !!d.summary.breaking && !broken // API restored after a detection
  const D = stale ? null : d, F = stale ? null : f
  const fixLabel = s.no_pr ? "Generate fix" : "Fix and open pull request"
  if (s.busy === "detect") return { tone: "run", title: "Checking the API…", sub: "Comparing the live spec with the saved baseline." }
  if (s.busy === "fix") return { tone: "run", title: "Writing the fix…", sub: "Finding the affected code, asking the model, checking the patch" + (s.no_pr ? "." : ", then opening the pull request.") }
  if (D && !D.ok) return { tone: "bad", title: "Detector failed.", sub: lastLine(D.out), act: ["detect", "Run detector again"] }
  if (F && !F.ok) return { tone: "bad", title: "The fix failed.", sub: lastLine(F.out), act: ["fix", "Try again"] }
  if (F?.pr) return { tone: "ok", title: "Pull request opened.", sub: "The fix, the explanation and the check result are waiting for review.", link: F.pr }
  if (F?.patch) return { tone: "ok", title: "The fix is ready.", sub: tidy(F.checks) || "Review the patch below." }
  if (F?.none) return { tone: "idle", title: "Nothing to fix.", sub: "No code in the repo uses what changed." }
  if (D?.summary.breaking) return { tone: "bad", title: "Change detected.", sub: `${plural(D.summary.breaking)} in the API. Next, the model writes the fix.`, act: ["fix", fixLabel] }
  if (broken) return { tone: "bad", title: "The API changed.", sub: crash ? "Your app is crashing. Run the detector to find out why." : "Run the detector to see what changed.", act: ["detect", "Run detector"] }
  if (stale) return { tone: "idle", title: "API restored.", sub: "Reset the demo to start again.", act: ["restart", "Reset demo"] }
  if (!D) return { tone: "ok", title: "Everything works.", sub: "Save the API’s current shape as a baseline first.", act: ["detect", "Save baseline"] }
  return { tone: "ok", title: "Baseline saved.", sub: "Now break the API and watch what happens.", act: ["break", "Break the API"] }
}

/** How far along the five-stage story we are: 0 baseline … 4 pull request. Returns [done count, active index]. */
export function progress(s: State): number {
  const d = s.detect, f = s.fix
  const stale = !!d && !!d.summary.breaking && !isBroken(s)
  if (stale || (!d && !isBroken(s))) return 0
  if (f?.pr) return 5
  if (f?.patch) return 4
  if (d?.summary.breaking) return 3
  if (isBroken(s)) return 2
  return 1
}

/** Polls dashboard.py. If nothing answers (static hosting, backend not started) falls back to a recorded sample. */
export function useConsole() {
  const [state, setState] = useState<State | null>(null)
  const [live, setLive] = useState<boolean | null>(null)

  const poll = useCallback(async () => {
    try {
      const r = await fetch("/state", { cache: "no-store" })
      const j = await r.json()
      if (!r.ok || !("busy" in j)) throw new Error("not the console API")
      setState(j as State)
      setLive(true)
    } catch {
      setState(sample as State)
      setLive(false)
    }
  }, [])

  useEffect(() => {
    poll()
    const id = setInterval(poll, 1500)
    return () => clearInterval(id)
  }, [poll])

  const act = useCallback(async (name: string) => {
    try { await fetch(`/do/${name}`, { method: "POST" }) } catch { /* backend gone: next poll switches to sample */ }
    poll()
  }, [poll])

  return { state, live, act }
}
