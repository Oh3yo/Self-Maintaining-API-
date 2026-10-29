import { useEffect, useState } from "react"
import { ArrowUpRight, Moon, Sun } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Console } from "@/components/console"
import { Demo } from "@/components/demo"
import { AUTHOR, REAL_PR_URL, REPO_URL } from "@/config"

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"))
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark)
    try { localStorage.setItem("theme", dark ? "dark" : "light") } catch { /* private window */ }
  }, [dark])
  return (
    <Button variant="ghost" className="size-9 px-0" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setDark(d => !d)}>
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )
}

function Header() {
  const link = "hidden rounded-md px-3 py-2 text-sm text-muted-foreground transition hover:text-foreground sm:block"
  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-1 px-6">
        <a href="#top" className="mr-auto font-semibold tracking-tight" translate="no">Self-Maintaining API</a>
        <a className={link} href="#console">Console</a>
        <a className={link} href="#pipeline">Pipeline</a>
        <a className={link} href="#real-run">Real run</a>
        <a className={link} href={REPO_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
        <ThemeToggle />
      </div>
    </header>
  )
}

function Hero() {
  return (
    <section id="top" className="mx-auto grid max-w-5xl items-center gap-12 px-6 py-16 md:py-24 lg:grid-cols-5">
      <div className="space-y-6 lg:col-span-3">
        <p className="inline-flex rounded-full border px-3 py-1 text-sm text-muted-foreground">Nebius × NVIDIA Global AI Hackathon</p>
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl">Your API changed. The fix is already in review.</h1>
        <p className="max-w-xl text-lg text-muted-foreground">
          Self-Maintaining API detects breaking changes in the APIs your code depends on, finds the lines they break, has an NVIDIA Nemotron model on Nebius Token Factory write the patch, checks it, and opens the pull request.
        </p>
        <div className="flex flex-wrap gap-3">
          <Button size="lg" onClick={() => document.getElementById("console")?.scrollIntoView({ behavior: "smooth" })}>Try the live console</Button>
          <Button size="lg" variant="outline" onClick={() => window.open(REAL_PR_URL, "_blank", "noopener,noreferrer")}>See a real pull request <ArrowUpRight className="size-4" /></Button>
        </div>
      </div>
      <Card className="relative overflow-hidden lg:col-span-2">
        <CardContent className="relative p-0">
          <div className="relative border-b px-4 py-3">
            <div className="absolute left-3 top-2 flex gap-1" aria-hidden>
              {[0, 1, 2].map(i => <span key={i} className="block size-2 rounded-full border dark:bg-white/10" />)}
            </div>
            <p className="pt-2 font-mono text-xs text-muted-foreground" translate="no">client.py · fix.patch</p>
          </div>
          <pre translate="no" className="py-4 font-mono text-[13px] leading-7">
            <span className="block px-4 text-muted-foreground">def user_email(user_id):</span>
            <span className="block px-4 text-muted-foreground">    user = get_user(user_id)</span>
            <span className="block bg-destructive/10 px-4 text-destructive">-    return user["email"]</span>
            <span className="block bg-primary/15 px-4 text-primary-800 dark:text-primary-300">+    return user["email_address"]</span>
          </pre>
          <p className="border-t px-4 py-3 text-sm text-muted-foreground">The API renamed <code className="font-mono text-xs">email</code> to <code className="font-mono text-xs">email_address</code>. This is the whole patch.</p>
        </CardContent>
      </Card>
    </section>
  )
}

function RealRun() {
  return (
    <section id="real-run" className="mx-auto grid max-w-5xl scroll-mt-16 items-center gap-10 px-6 py-16 md:py-24 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-2">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Opened by the pipeline, not by hand</h2>
        <p className="text-muted-foreground">
          This is pull request #2 on the demo repo. The description lists the upstream change, the model’s explanation and the validation result, and names the model that wrote the fix.
        </p>
        <a className="inline-flex items-center gap-1 text-sm font-medium text-primary-700 underline-offset-4 hover:underline dark:text-primary-400" href={REAL_PR_URL} target="_blank" rel="noopener noreferrer">
          Open it on GitHub <ArrowUpRight className="size-4" />
        </a>
      </div>
      <Card className="overflow-hidden lg:col-span-3">
        <img src="/pr-2.png" width={1429} height={913} loading="lazy" decoding="async" className="h-auto w-full"
          alt="GitHub pull request description with sections Upstream API changes, Fix and Validation, generated using nvidia/nemotron-3-super-120b-a12b on Nebius Token Factory." />
      </Card>
    </section>
  )
}

const LIMITS = [
  ["Removed endpoints", "are flagged, but a human has to decide what replaces them."],
  ["Renames", "are a heuristic: one field removed and one added in the same object."],
  ["Field matching", "is noisy when the code never names the schema."],
  ["JavaScript repos", "mostly skip validation, because node_modules is not copied."],
  ["Testing", "so far covers a small demo repo, not production codebases."],
]

function Limits() {
  return (
    <section className="mx-auto max-w-5xl px-6 pb-16 md:pb-24">
      <Card>
        <CardContent className="grid gap-8 pt-6 lg:grid-cols-5">
          <div className="space-y-2 lg:col-span-2">
            <h2 className="text-2xl font-semibold tracking-tight">What it can’t do yet</h2>
            <p className="text-muted-foreground">Known limits, so nobody has to find them by surprise.</p>
          </div>
          <ul className="space-y-3 lg:col-span-3">
            {LIMITS.map(([k, v]) => <li key={k} className="border-b pb-3 last:border-0 last:pb-0"><span className="font-medium">{k}</span> <span className="text-muted-foreground">{v}</span></li>)}
          </ul>
        </CardContent>
      </Card>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-8 text-sm text-muted-foreground">
        <span>Built by {AUTHOR} for the Nebius × NVIDIA Global AI Hackathon.</span>
        <a className="underline-offset-4 hover:text-foreground hover:underline" href={REPO_URL} target="_blank" rel="noopener noreferrer">Source on GitHub</a>
        <span className="basis-full text-xs">Independent project. Nebius and NVIDIA are trademarks of their owners.</span>
      </div>
    </footer>
  )
}

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Console />
        <Demo />
        <RealRun />
        <Limits />
      </main>
      <Footer />
    </>
  )
}
