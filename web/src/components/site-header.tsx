import Link from "next/link"
import { Button } from "@/components/ui/button"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6">
        <Link href="/" className="font-heading text-[15px] font-semibold tracking-tight">
          Self-Maintaining API
        </Link>
        <nav className="hidden items-center gap-5 text-sm text-muted-foreground sm:flex">
          <Link href="/#features" className="hover:text-foreground">
            Pipeline
          </Link>
          <Link href="/#how" className="hover:text-foreground">
            How it works
          </Link>
          <Link href="/dashboard" className="hover:text-foreground">
            Live console
          </Link>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/#how">Docs</Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/dashboard">Open dashboard</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
