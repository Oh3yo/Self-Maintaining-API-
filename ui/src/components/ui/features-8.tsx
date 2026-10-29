import { FileDiff, GitBranch, GitCommit, GitPullRequest, ShieldCheck } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"

/* Adapted from the features-8 bento reference: same grid, cards, ring icons, window and timeline,
   rewritten around the real five stages of the pipeline. */

const BLOB =
  "M112.891 97.7022C140.366 97.0802 171.004 94.6715 201.087 87.5116C210.43 85.2881 219.615 82.6412 228.284 78.2473C232.198 76.3179 235.905 73.9942 239.348 71.3124C241.85 69.2557 243.954 66.7571 245.555 63.9408C249.34 57.3235 248.281 50.5341 242.498 45.6109C239.033 42.7237 235.228 40.2703 231.169 38.3054C219.443 32.7209 207.141 28.4382 194.482 25.534C184.013 23.1927 173.358 21.7755 162.64 21.2989C161.376 21.3512 160.113 21.181 158.908 20.796C158.034 20.399 156.857 19.1682 156.962 18.4535C157.115 17.8927 157.381 17.3689 157.743 16.9139C158.104 16.4588 158.555 16.0821 159.067 15.8066C160.14 15.4683 161.274 15.3733 162.389 15.5286C179.805 15.3566 196.626 18.8373 212.998 24.462C220.978 27.2494 228.798 30.4747 236.423 34.1232C240.476 36.1159 244.202 38.7131 247.474 41.8258C254.342 48.2578 255.745 56.9397 251.841 65.4892C249.793 69.8582 246.736 73.6777 242.921 76.6327C236.224 82.0192 228.522 85.4602 220.502 88.2924C205.017 93.7847 188.964 96.9081 172.738 99.2109C153.442 101.949 133.993 103.478 114.506 103.79C91.1468 104.161 67.9334 102.97 45.1169 97.5831C36.0094 95.5616 27.2626 92.1655 19.1771 87.5116C13.839 84.5746 9.1557 80.5802 5.41318 75.7725C-0.54238 67.7259 -1.13794 59.1763 3.25594 50.2827C5.82447 45.3918 9.29572 41.0315 13.4863 37.4319C24.2989 27.5721 37.0438 20.9681 50.5431 15.7272C68.1451 8.8849 86.4883 5.1395 105.175 2.83669C129.045 0.0992292 153.151 0.134761 177.013 2.94256C197.672 5.23215 218.04 9.01724 237.588 16.3889C240.089 17.3418 242.498 18.5197 244.933 19.6446C246.627 20.4387 247.725 21.6695 246.997 23.615C246.455 25.1105 244.814 25.5605 242.63 24.5811C230.322 18.9961 217.233 16.1904 204.117 13.4376C188.761 10.3438 173.2 8.36665 157.558 7.52174C129.914 5.70776 102.154 8.06792 75.2124 14.5228C60.6177 17.8788 46.5758 23.2977 33.5102 30.6161C26.6595 34.3329 20.4123 39.0673 14.9818 44.658C12.9433 46.8071 11.1336 49.1622 9.58207 51.6855C4.87056 59.5336 5.61172 67.2494 11.9246 73.7608C15.2064 77.0494 18.8775 79.925 22.8564 82.3236C31.6176 87.7101 41.3848 90.5291 51.3902 92.5804C70.6068 96.5773 90.0219 97.7419 112.891 97.7022Z"

const Ring = ({ children, size = "size-12" }: { children: React.ReactNode; size?: string }) => (
  <div className={`relative flex aspect-square ${size} rounded-full border before:absolute before:-inset-2 before:rounded-full before:border dark:border-white/10 dark:before:border-white/5`}>
    {children}
  </div>
)

const Copy = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <div className="space-y-2">
    <h3 className="text-lg font-medium">{title}</h3>
    <p className="text-muted-foreground">{children}</p>
  </div>
)

const WindowDots = () => (
  <div className="absolute left-3 top-2 flex gap-1" aria-hidden>
    {[0, 1, 2].map(i => <span key={i} className="block size-2 rounded-full border dark:border-white/10 dark:bg-white/10" />)}
  </div>
)

const step = "block h-fit rounded border bg-card px-2 py-1 font-mono text-xs whitespace-nowrap shadow-sm"
const node = "grid place-items-center rounded-full bg-muted ring-background ring-4"

export function Features() {
  return (
    <section id="pipeline" className="scroll-mt-16 bg-gray-50 py-16 md:py-32 dark:bg-transparent">
      <div className="mx-auto max-w-3xl px-6 lg:max-w-5xl">
        <div className="mb-10 max-w-xl space-y-3">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">Five stages, one pull request</h2>
          <p className="text-muted-foreground">Each stage is a small Python module you can run on its own. Together they take an API change from detection to review.</p>
        </div>
        <div className="relative">
          <div className="relative z-10 grid grid-cols-6 gap-3">
            <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2">
              <CardContent className="pt-6">
                <div className="mx-auto grid size-32 place-items-center">
                  <Ring size="size-32"><FileDiff className="m-auto size-12" strokeWidth={1} /></Ring>
                </div>
                <div className="relative z-10 mt-8 text-center">
                  <Copy title="1. Detector">Diffs OpenAPI specs, changelogs and SDK versions against a saved baseline. Only breaking changes move on.</Copy>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden sm:col-span-3 lg:col-span-2">
              <CardContent className="pt-6">
                <div className="pt-6 lg:px-2">
                  <div className="relative rounded-lg border bg-muted/50 p-4 pt-8 font-mono text-xs leading-relaxed" translate="no">
                    <WindowDots />
                    <div className="text-muted-foreground">client.py</div>
                    <div className="text-muted-foreground">12  user = get_user(user_id)</div>
                    <div className="-mx-2 rounded bg-primary/15 px-2 text-primary-800 dark:text-primary-300">13  return user["email"]</div>
                  </div>
                </div>
                <div className="relative z-10 mt-10 text-center">
                  <Copy title="2. Impact scanner">Finds the exact lines that use what changed. Python is read with the AST, other languages with a regex fallback.</Copy>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full flex overflow-hidden lg:col-span-2">
              <CardContent className="relative m-auto size-fit pt-6">
                <div className="relative flex h-24 w-56 items-center">
                  <svg className="text-muted absolute inset-0 size-full" viewBox="0 0 254 104" fill="none" aria-hidden>
                    <path d={BLOB} fill="currentColor" />
                  </svg>
                  <span className="mx-auto block w-fit text-5xl font-semibold">1 line</span>
                </div>
                <h3 className="mt-6 text-center text-xl font-semibold">3. Fix generator</h3>
                <p className="mx-auto mt-2 max-w-[22rem] text-center text-muted-foreground">A Nemotron model on Nebius Token Factory returns edits, not a diff. Anything outside the flagged lines is rejected, so the demo fix is a single line.</p>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden lg:col-span-3">
              <CardContent className="grid pt-6 sm:grid-cols-2">
                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                  <Ring><ShieldCheck className="m-auto size-5" strokeWidth={1} /></Ring>
                  <Copy title="4. Validator">The patch is applied to a temporary copy and the repo’s tests or lint run on it. A failure goes back to the model, up to three tries.</Copy>
                </div>
                <div className="relative -mb-6 -mr-6 mt-6 h-fit rounded-tl-(--radius) border-l border-t bg-muted/50 p-6 pt-8 py-6 sm:ml-6">
                  <WindowDots />
                  <div className="space-y-2 font-mono text-xs leading-relaxed" translate="no">
                    <div className="text-muted-foreground">$ python -m compileall -q .</div>
                    <div className="text-primary-800 dark:text-primary-300">Passed on a temp copy with the patch applied.</div>
                    <div className="pt-3 text-muted-foreground">Failing before the patch? Reported as pre-existing, not blamed on the fix.</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="relative col-span-full overflow-hidden lg:col-span-3">
              <CardContent className="grid h-full pt-6 sm:grid-cols-2">
                <div className="relative z-10 flex flex-col justify-between space-y-12 lg:space-y-6">
                  <Ring><GitPullRequest className="m-auto size-6" strokeWidth={1} /></Ring>
                  <Copy title="5. Pull request bot">Pushes a branch, commits the patch and opens a pull request that explains the change and the check result.</Copy>
                </div>
                <div className="relative mt-6 before:absolute before:inset-0 before:mx-auto before:w-px before:bg-(--color-border) sm:-my-6 sm:-mr-6">
                  <div className="relative flex h-full flex-col justify-center space-y-6 py-6" translate="no">
                    <div className="relative flex w-[calc(50%+0.875rem)] items-center justify-end gap-2">
                      <span className={step}>api-fix/&lt;time&gt;</span>
                      <div className={`${node} size-7`}><GitBranch className="size-3.5" /></div>
                    </div>
                    <div className="relative ml-[calc(50%-1rem)] flex items-center gap-2">
                      <div className={`${node} size-8`}><GitCommit className="size-4" /></div>
                      <span className={step}>5fb39f8</span>
                    </div>
                    <div className="relative flex w-[calc(50%+0.875rem)] items-center justify-end gap-2">
                      <span className={step}>Pull request #2</span>
                      <div className={`${node} size-7`}><GitPullRequest className="size-3.5" /></div>
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
