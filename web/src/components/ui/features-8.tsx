import { Card, CardContent } from "@/components/ui/card"
import { Shield, Users } from "lucide-react"

const AVATARS = [
  {
    name: "Detector",
    src: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?auto=format&fit=crop&w=80&h=80&q=80",
  },
  {
    name: "Scanner",
    src: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=80&h=80&q=80",
  },
  {
    name: "Reviewer",
    src: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=80&h=80&q=80",
  },
]

export function Features() {
  return (
    <section id="features" className="bg-gray-50 py-16 md:py-32 dark:bg-transparent">
      <div className="mx-auto max-w-3xl px-6 lg:max-w-5xl">
        <div className="relative">
          <div className="relative z-10 grid grid-cols-6 gap-3">
            <Card className="relative col-span-full flex overflow-hidden lg:col-span-2">
              <CardContent className="relative m-auto size-fit pt-6">
                <div className="relative flex h-24 w-56 items-center">
                  <svg
                    className="text-muted-foreground/40 absolute inset-0 size-full"
                    viewBox="0 0 254 104"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden="true"
                  >
                    <path
                      d="M112.891 97.7022C140.366 97.0802 171.004 94.6715 201.087 87.5116C210.43 85.2881 219.615 82.6412 228.284 78.2473C232.198 76.3179 235.905 73.9942 239.348 71.3124C241.85 69.2557 243.954 66.7571 245.555 63.9408C249.34 57.3235 248.281 50.5341 242.498 45.6109C239.033 42.7237 235.228 40.2703 231.169 38.3054C219.443 32.7209 207.141 28.4382 194.482 25.534C184.013 23.1927 173.358 21.7755 162.64 21.2989C161.376 21.3512 160.113 21.181 158.908 20.796C158.034 20.399 156.857 19.1682 156.962 18.4535C157.115 17.8927 157.381 17.3689 157.743 16.9139C158.104 16.4588 158.555 16.0821 159.067 15.8066C160.14 15.4683 161.274 15.3733 162.389 15.5286C179.805 15.3566 196.626 18.8373 212.998 24.462C220.978 27.2494 228.798 30.4747 236.423 34.1232C240.476 36.1159 244.202 38.7131 247.474 41.8258C254.342 48.2578 255.745 56.9397 251.841 65.4892C249.793 69.8582 246.736 73.6777 242.921 76.6327C236.224 82.0192 228.522 85.4602 220.502 88.2924C205.017 93.7847 188.964 96.9081 172.738 99.2109C153.442 101.949 133.993 103.478 114.506 103.79C91.1468 104.161 67.9334 102.97 45.1169 97.5831C36.0094 95.5616 27.2626 92.1655 19.1771 87.5116C13.839 84.5746 9.1557 80.5802 5.41318 75.7725C-0.54238 67.7259 -1.13794 59.1763 3.25594 50.2827C5.82447 45.3918 9.29572 41.0315 13.4863 37.4319C24.2989 27.5721 37.0438 20.9681 50.5431 15.7272C68.1451 8.8849 86.4883 5.1395 105.175 2.83669C129.045 0.0992292 153.151 0.134761 177.013 2.94256C197.672 5.23215 218.04 9.01724 237.588 16.3889C240.089 17.3418 242.498 18.5197 244.933 19.6446C246.627 20.4387 247.725 21.6695 246.997 23.615C246.455 25.1105 244.814 25.5605 242.63 24.5811C230.322 18.9961 217.233 16.1904 204.117 13.4376C188.761 10.3438 173.2 8.36665 157.558 7.52174C129.914 5.70776 102.154 8.06792 75.2124 14.5228C60.6177 17.8788 46.5758 23.2977 33.5102 30.6161C26.6595 34.3329 20.4123 39.0673 14.9818 44.658C12.9433 46.8071 11.1336 49.1622 9.58207 51.6855C4.87056 59.5336 5.61172 67.2494 11.9246 73.7608C15.2064 77.0494 18.8775 79.925 22.8564 82.3236C31.6176 87.7101 41.3848 90.5291 51.3902 92.5804C70.6068 96.5773 90.0219 97.7419 112.891 97.7022Z"
                      fill="currentColor"
                    />
                  </svg>
                  <span className="mx-auto block w-fit text-5xl font-semibold">100%</span>
                </div>
                <h2 className="mt-6 text-center text-3xl font-semibold">Spec coverage</h2>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2">
              <CardContent className="pt-6">
                <div className="relative mx-auto flex aspect-square size-32 rounded-full border before:absolute before:-inset-2 before:rounded-full before:border dark:border-white/10 dark:before:border-white/5">
                  <svg className="m-auto h-fit w-24" viewBox="0 0 212 143" fill="none" aria-hidden="true">
                    <circle
                      cx="106"
                      cy="90"
                      r="52"
                      className="text-zinc-400 dark:text-zinc-600"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="none"
                    />
                    <circle
                      cx="106"
                      cy="90"
                      r="32"
                      className="text-zinc-400 dark:text-zinc-600"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="none"
                    />
                    <circle cx="106" cy="90" r="12" className="text-primary" fill="currentColor" />
                    <path
                      className="text-primary"
                      d="M12 72H200"
                      stroke="currentColor"
                      strokeWidth="6"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
                <div className="relative z-10 mt-6 space-y-2 text-center">
                  <h2 className="text-lg font-medium transition dark:text-white">Breaking by default</h2>
                  <p className="text-foreground">
                    OpenAPI, changelogs, and SDK versions are classified as breaking, warning, or
                    info. Exit code 2 fails CI when the contract moves.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2">
              <CardContent className="pt-6">
                <div className="pt-6 lg:px-6">
                  <svg
                    className="dark:text-muted-foreground w-full"
                    viewBox="0 0 386 123"
                    fill="none"
                    aria-hidden="true"
                  >
                    <rect width="386" height="123" rx="10" className="text-muted/40" fill="currentColor" />
                    <path
                      className="text-primary"
                      d="M8 108 C 40 108, 48 72, 80 72 S 120 96, 152 88 S 200 40, 232 52 S 280 100, 312 84 S 360 70, 378 78"
                      stroke="currentColor"
                      strokeWidth="3"
                      fill="none"
                    />
                    <path
                      d="M8 108 C 40 108, 48 72, 80 72 S 120 96, 152 88 S 200 40, 232 52 S 280 100, 312 84 S 360 70, 378 108 L 8 108"
                      className="text-primary/15 dark:text-primary/35"
                      fill="currentColor"
                    />
                  </svg>
                </div>
                <div className="relative z-10 mt-14 space-y-2 text-center">
                  <h2 className="text-lg font-medium transition">Patch before clients fail</h2>
                  <p className="text-foreground">
                    The scanner finds every usage, the model writes one patch, then checks run
                    before a pull request opens.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden lg:col-span-3">
              <CardContent className="grid pt-6 sm:grid-cols-2">
                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                  <div className="relative flex aspect-square size-12 rounded-full border before:absolute before:-inset-2 before:rounded-full before:border dark:border-white/10 dark:before:border-white/5">
                    <Shield className="m-auto size-5" strokeWidth={1} />
                  </div>
                  <div className="space-y-2">
                    <h2 className="text-lg font-medium text-zinc-800 transition dark:text-white">
                      Impact scanner
                    </h2>
                    <p className="text-foreground">
                      Python AST for attributes, keys, and kwargs. Regex for other languages.
                      Confidence scores so a field named <code>id</code> does not light up the whole
                      repo.
                    </p>
                  </div>
                </div>
                <div className="relative mt-6 -mr-6 -mb-6 h-fit rounded-tl-[var(--radius)] border-t border-l p-6 py-6 sm:ml-6">
                  <div className="absolute top-2 left-3 flex gap-1">
                    <span className="block size-2 rounded-full border dark:border-white/10 dark:bg-white/10" />
                    <span className="block size-2 rounded-full border dark:border-white/10 dark:bg-white/10" />
                    <span className="block size-2 rounded-full border dark:border-white/10 dark:bg-white/10" />
                  </div>
                  <svg className="w-full sm:w-[150%]" viewBox="0 0 366 160" fill="none" aria-hidden="true">
                    <path
                      className="text-primary/15 dark:text-primary/35"
                      d="M0 160 L0 110 L20 90 L40 120 L70 40 L90 70 L120 20 L160 80 L200 10 L240 60 L280 30 L320 90 L366 50 L366 160 Z"
                      fill="currentColor"
                    />
                    <path
                      className="text-primary"
                      d="M0 110 L20 90 L40 120 L70 40 L90 70 L120 20 L160 80 L200 10 L240 60 L280 30 L320 90 L366 50"
                      stroke="currentColor"
                      strokeWidth="2"
                      fill="none"
                    />
                  </svg>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden lg:col-span-3">
              <CardContent className="grid h-full pt-6 sm:grid-cols-2">
                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                  <div className="relative flex aspect-square size-12 rounded-full border before:absolute before:-inset-2 before:rounded-full before:border dark:border-white/10 dark:before:border-white/5">
                    <Users className="m-auto size-6" strokeWidth={1} />
                  </div>
                  <div className="space-y-2">
                    <h2 className="text-lg font-medium transition">Humans still merge</h2>
                    <p className="text-foreground">
                      The pull request carries the explanation and the check result. Nothing lands
                      on main until someone reviews it.
                    </p>
                  </div>
                </div>
                <div className="relative mt-6 before:absolute before:inset-0 before:mx-auto before:w-px before:bg-[var(--color-border)] sm:-my-6 sm:-mr-6">
                  <div className="relative flex h-full flex-col justify-center space-y-6 py-6">
                    <div className="relative flex w-[calc(50%+0.875rem)] items-center justify-end gap-2">
                      <span className="block h-fit rounded border px-2 py-1 text-xs shadow-sm">
                        {AVATARS[0].name}
                      </span>
                      <div className="ring-background size-7 ring-4">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img className="size-full rounded-full object-cover" src={AVATARS[0].src} alt="" />
                      </div>
                    </div>
                    <div className="relative ml-[calc(50%-1rem)] flex items-center gap-2">
                      <div className="ring-background size-8 ring-4">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img className="size-full rounded-full object-cover" src={AVATARS[1].src} alt="" />
                      </div>
                      <span className="block h-fit rounded border px-2 py-1 text-xs shadow-sm">
                        {AVATARS[1].name}
                      </span>
                    </div>
                    <div className="relative flex w-[calc(50%+0.875rem)] items-center justify-end gap-2">
                      <span className="block h-fit rounded border px-2 py-1 text-xs shadow-sm">
                        {AVATARS[2].name}
                      </span>
                      <div className="ring-background size-7 ring-4">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img className="size-full rounded-full object-cover" src={AVATARS[2].src} alt="" />
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </section>
  )
}
