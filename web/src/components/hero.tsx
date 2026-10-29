import Link from "next/link"
import { Button } from "@/components/ui/button"

export function Hero() {
  return (
    <section className="relative overflow-hidden bg-[#dce7dd]">
      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-20 md:grid-cols-[minmax(0,1fr)_minmax(0,420px)] md:py-28">
        <div>
          <p className="text-sm font-medium text-[#3d4650]">Watch · diff · patch · PR</p>
          <h1 className="font-heading mt-4 max-w-[16ch] text-5xl font-extrabold tracking-tight text-[#11161c] md:text-7xl md:leading-[0.95]">
            When the API moves, the client follows.
          </h1>
          <p className="mt-6 max-w-[36ch] text-lg leading-7 text-[#3d4650]">
            A change detector, impact scanner, and fix generator for third-party APIs. Break the
            mock, watch the app crash, then let the pipeline open the pull request.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button size="lg" className="rounded-full px-6" asChild>
              <Link href="/dashboard">Open the live console</Link>
            </Button>
            <Button size="lg" variant="outline" className="rounded-full px-6 bg-white/60" asChild>
              <Link href="/#features">See the pipeline</Link>
            </Button>
          </div>
        </div>
        <pre className="overflow-auto rounded-none bg-[#11161c] p-6 font-mono text-[13px] leading-6 text-[#d7e0ee] md:self-end">
          {`GET /v1/users/1
{
  "id": 1,
  "`}
          <span className="bg-[#7ee0a0] px-1 font-bold text-[#11161c]">email</span>
          {`": "tsu@example.com"
}`}
        </pre>
      </div>
    </section>
  )
}
