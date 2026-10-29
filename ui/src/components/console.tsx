import { useEffect, useRef, useState, type ReactNode } from "react"
import { ArrowUpRight, Check, FlaskConical, Loader2, Radio } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { isBroken, plan, progress, useConsole, type State, type Tone } from "@/lib/console"

const STEPS = ["Baseline", "Break", "Detect", "Fix", "Pull request"]

const dotClass: Record<Tone, string> = {
  idle: "bg-muted-foreground/40",
  ok: "bg-primary-600 dark:bg-primary-500",
  bad: "bg-destructive",
  run: "bg-blue-500 animate-pulse",
}

function Dot({ tone }: { tone: Tone }) {
  return <span aria-hidden className={cn("inline-block size-2.5 shrink-0 rounded-full", dotClass[tone])} />
}

function StageCard({ title, status, tone, className, children, actions }: {
  title: string; status: string; tone: Tone; className?: string; children: ReactNode; actions?: ReactNode
}) {
  return (
    <Card className={cn("col-span-full overflow-hidden", className)}>
      <CardContent className="space-y-4 pt-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <Dot tone={tone} />
          <h3 className="text-lg font-medium">{title}</h3>
          <span className="text-sm text-muted-foreground tabular-nums">{status}</span>
          <div className="ml-auto flex gap-2">{actions}</div>
        </div>
        {children}
      </CardContent>
    </Card>
  )
}

const Hint = ({ children }: { children: ReactNode }) => <p className="max-w-prose text-sm text-muted-foreground">{children}</p>
const Pre = ({ children, className }: { children: ReactNode; className?: string }) => (
  <pre translate="no" className={cn("overflow-auto rounded-md border bg-muted/60 p-4 font-mono text-[13px] leading-relaxed whitespace-pre-wrap break-words", className)}>{children}</pre>
)

function Diff({ patch }: { patch: string }) {
  return (
    <Pre className="p-0 py-3">
      {patch.replace(/\n$/, "").split("\n").map((l, i) => {
        const c = /^(\+\+\+|---|@@)/.test(l) ? "text-muted-foreground" : l[0] === "+" ? "bg-primary/15 text-primary-800 dark:text-primary-300" : l[0] === "-" ? "bg-destructive/10 text-destructive" : ""
        return <span key={i} className={cn("block min-h-[1.6em] px-4", c)}>{l}</span>
      })}
    </Pre>
  )
}

function Stepper({ done, busy }: { done: number; busy: boolean }) {
  return (
    <ol className="flex flex-wrap gap-x-5 gap-y-3" aria-label="Pipeline progress">
      {STEPS.map((name, i) => {
        const complete = i < done, active = i === done
        return (
          <li key={name} className="flex items-center gap-2 text-sm" aria-current={active ? "step" : undefined}>
            <span className={cn(
              "grid size-6 place-items-center rounded-full border text-xs font-medium tabular-nums",
              complete && "border-transparent bg-primary text-primary-foreground",
              active && "border-primary text-foreground ring-4 ring-primary/15",
              !complete && !active && "text-muted-foreground",
            )}>
              {complete ? <Check className="size-3.5" strokeWidth={3} /> : active && busy ? <Loader2 className="size-3.5 animate-spin" /> : i + 1}
            </span>
            <span className={cn(complete || active ? "text-foreground" : "text-muted-foreground")}>{name}</span>
          </li>
        )
      })}
    </ol>
  )
}

function ResetButton({ off, onConfirm }: { off: boolean; onConfirm: () => void }) {
  const [armed, setArmed] = useState(false)
  const t = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(t.current), [])
  return (
    <Button variant="ghost" disabled={off} onClick={() => {
      if (!armed) { setArmed(true); t.current = setTimeout(() => setArmed(false), 3000); return }
      clearTimeout(t.current); setArmed(false); onConfirm()
    }}>
      {armed ? "Click again to reset" : "Reset demo"}
    </Button>
  )
}

function Body({ s, live, act }: { s: State; live: boolean; act: (n: string) => void }) {
  const p = plan(s), done = progress(s)
  const off = !!s.busy || !live
  const d = s.detect, f = s.fix, broken = isBroken(s)
  const crash = /crashed/.test(s.app), works = /->/.test(s.app)

  const dTone: Tone = s.busy === "detect" ? "run" : !d ? "idle" : !d.ok ? "bad" : d.summary.breaking ? "bad" : "ok"
  const dStatus = s.busy === "detect" ? "Running…" : !d ? "Not run yet" : !d.ok ? "Failed"
    : d.summary.breaking ? `${d.summary.breaking} breaking` : d.status.includes("baseline") ? "Baseline saved" : "No changes"
  const fTone: Tone = s.busy === "fix" ? "run" : !f ? "idle" : !f.ok ? "bad" : f.none ? "idle" : "ok"
  const fStatus = s.busy === "fix" ? "Working…" : !f ? "Not run yet" : !f.ok ? "Failed" : f.none ? "Nothing to fix" : "Patch ready"

  return (
    <div className="relative z-10 grid grid-cols-6 gap-3">
      <Card className="col-span-full lg:col-span-3">
        <CardContent className="flex h-full flex-col gap-6 pt-6">
          <Stepper done={done} busy={!!s.busy} />
          <div aria-live="polite" className="space-y-2">
            <div className="flex items-center gap-3"><Dot tone={p.tone} /><h3 className="text-3xl font-semibold tracking-tight sm:text-4xl">{p.title}</h3></div>
            <p className="max-w-prose text-muted-foreground tabular-nums">{p.sub}</p>
          </div>
          <div className="mt-auto flex flex-wrap items-center gap-3">
            {p.link ? (
              <Button size="lg" onClick={() => window.open(p.link, "_blank", "noopener,noreferrer")}>Open pull request <ArrowUpRight className="size-4" /></Button>
            ) : p.act ? (
              <Button size="lg" disabled={off} onClick={() => act(p.act![0])}>{p.act[1]}</Button>
            ) : null}
            {live && <ResetButton off={!!s.busy} onConfirm={() => act("restart")} />}
            {s.no_pr && live && <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">Rehearsal: no pull requests</span>}
          </div>
        </CardContent>
      </Card>

      <Card className="col-span-full overflow-hidden lg:col-span-3">
        <CardContent className="flex h-full flex-col pt-6">
          <div className="relative -mx-6 -mt-0 border-b px-6 pb-3">
            <div className="absolute left-3 top-1 flex gap-1" aria-hidden>
              {[0, 1, 2].map(i => <span key={i} className="block size-2 rounded-full border dark:bg-white/10" />)}
            </div>
            <p className="pt-3 font-mono text-xs text-muted-foreground" translate="no">GET localhost:8000/v1/users/1</p>
          </div>
          <pre translate="no" className="my-4 overflow-x-auto font-mono text-[13px] leading-relaxed">{`{\n  "id": 1,\n  "`}<b className={cn("rounded px-1 font-semibold", broken ? "bg-destructive/15 text-destructive" : "bg-primary/15 text-primary-700 dark:text-primary-400")}>{s.field}</b>{`": "tsu@example.com"\n}`}</pre>
          <div className="mt-auto flex flex-wrap gap-2">
            <Button variant="outline" disabled={off || broken} onClick={() => act("break")}>Break the API</Button>
            <Button variant="outline" disabled={off || !broken} onClick={() => act("reset")}>Restore</Button>
          </div>
        </CardContent>
      </Card>

      <StageCard className="lg:col-span-3" title="Your app" tone={crash ? "bad" : works ? "ok" : "idle"} status={crash ? "Crashing" : works ? "Working" : "Checking…"}>
        <Pre>{s.app || "…"}</Pre>
        {works && broken && f?.pr && <Hint>This is the fixed code from the pull request branch, running against the changed API.</Hint>}
      </StageCard>

      <StageCard className="lg:col-span-3" title="Change detector" tone={dTone} status={dStatus}
        actions={<Button variant="outline" disabled={off} onClick={() => act("detect")}>Run detector</Button>}>
        {!d ? <Hint>Run it once while the API is stable to save a baseline, then again after you break it.</Hint>
          : !d.ok ? <Pre>{d.out}</Pre>
          : d.changes.length ? (
            <ul className="space-y-3">
              {d.changes.map((c, i) => (
                <li key={i} className="space-y-1 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", c.severity === "breaking" ? "bg-destructive/15 text-destructive" : "bg-muted text-muted-foreground")}>{c.severity}</span>
                    <code translate="no" className="font-mono text-xs break-all">{c.location}</code>
                  </div>
                  <p className="text-muted-foreground">{c.message}</p>
                </li>
              ))}
            </ul>
          ) : <Hint>{d.status.includes("baseline") ? "Saved the current API as the baseline." : "The API matches the saved baseline."}</Hint>}
      </StageCard>

      <StageCard title="Fix generator" tone={fTone} status={fStatus}
        actions={<Button variant="outline" disabled={off || !d} onClick={() => act("fix")}>{s.no_pr ? "Generate fix" : "Fix and open PR"}</Button>}>
        {f && !f.ok ? <Pre>{f.out}</Pre>
          : f?.none ? <Hint>{f.out.trim()}</Hint>
          : f ? (
            <div className="grid gap-6 lg:grid-cols-5">
              <dl className="space-y-5 text-sm lg:col-span-2">
                <div><dt className="text-muted-foreground">Upstream change</dt>{f.changes.map((c, i) => <dd key={i} className="mt-1">{c}</dd>)}</div>
                <div><dt className="text-muted-foreground">Fix from <span translate="no" className="font-mono text-xs">{f.model}</span></dt><dd className="mt-1">{f.summary}</dd></div>
                <div><dt className="text-muted-foreground">Files changed</dt><dd className="mt-1"><code translate="no" className="font-mono text-xs">{f.files}</code></dd></div>
                <div><dt className="text-muted-foreground">Checks</dt>
                  <dd className="mt-1">{f.checks ? <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-0.5 text-primary-800 dark:text-primary-300"><Check className="size-3.5" strokeWidth={3} />{f.checks.replace(/`/g, "")}</span> : "None ran"}</dd></div>
              </dl>
              <div className="lg:col-span-3"><Diff patch={f.patch} /></div>
            </div>
          ) : <Hint>Finds the code that uses the changed API, asks the model for a fix, and checks it before opening a pull request.</Hint>}
      </StageCard>

      <StageCard title="Pull request" tone={f?.pr ? "ok" : "idle"} status={f?.pr ? "Opened" : s.no_pr && f?.patch ? "Skipped in rehearsal" : "Waiting"}>
        {f?.pr
          ? <a href={f.pr} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-mono text-sm break-all text-primary-700 underline-offset-4 hover:underline dark:text-primary-400">{f.pr}<ArrowUpRight className="size-4 shrink-0" /></a>
          : <Hint>The fix, an explanation and the check result land here as a pull request for review.</Hint>}
      </StageCard>
    </div>
  )
}

export function Console() {
  const { state, live, act } = useConsole()
  return (
    <section id="console" className="scroll-mt-16 border-y bg-muted/40 py-16 md:py-24">
      <div className="mx-auto max-w-3xl px-6 lg:max-w-5xl">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-xl space-y-3">
            <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Break the API. Watch it get fixed.</h2>
            <p className="text-muted-foreground">Every card below is the real pipeline: the detector, the scanner, the model and the validator running in this repo.</p>
          </div>
          {live !== null && (
            <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm", live ? "text-primary-700 dark:text-primary-400" : "text-muted-foreground")}>
              {live ? <Radio className="size-4" /> : <FlaskConical className="size-4" />}
              {live ? "Live: connected to dashboard.py" : "Sample run: start dashboard.py to go live"}
            </span>
          )}
        </div>
        {state && <Body s={state} live={!!live} act={act} />}
      </div>
    </section>
  )
}
