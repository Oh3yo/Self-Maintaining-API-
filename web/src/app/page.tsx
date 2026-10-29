import { Demo } from "@/components/ui/demo"
import { Hero } from "@/components/hero"
import { HowItWorks } from "@/components/how-it-works"
import { SiteFooter } from "@/components/site-footer"
import { SiteHeader } from "@/components/site-header"
import { Button } from "@/components/ui/button"
import Link from "next/link"

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <Demo />
        <HowItWorks />
        <section className="bg-[#11161c] px-6 py-16 text-[#d7e0ee]">
          <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-6 md:flex-row md:items-center">
            <div>
              <h2 className="font-heading text-3xl font-semibold tracking-tight text-white">
                Drive the same demo the Python console already has.
              </h2>
              <p className="mt-2 max-w-xl text-sm leading-6 text-[#9aa6b8]">
                Break the mock field from email to email_address, run the detector, then generate the
                fix. Needs the Python process on port 8001.
              </p>
            </div>
            <Button size="lg" className="rounded-full bg-white text-[#11161c] hover:bg-white/90" asChild>
              <Link href="/dashboard">Open dashboard</Link>
            </Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  )
}
