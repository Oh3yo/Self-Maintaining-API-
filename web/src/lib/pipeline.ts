export type DetectChange = {
  severity: string
  location: string
  message: string
}

export type DetectView = {
  ok: boolean
  out: string
  summary: { breaking: number; warning: number; info: number; errors: number }
  status: string[]
  changes: DetectChange[]
}

export type FixView = {
  ok: boolean
  out: string
  none: boolean
  changes: string[]
  model: string | null
  summary: string | null
  files: string | null
  checks: string | null
  pr: string | null
  patch: string
}

export type PipelineState = {
  busy: string | null
  field: string
  app: string
  no_pr: boolean
  detect: DetectView | null
  fix: FixView | null
  offline?: boolean
}

export const OFFLINE_STATE: PipelineState = {
  busy: null,
  field: "email",
  app: "GET /v1/users/1 -> { id: 1, email: 'tsu@example.com' }",
  no_pr: false,
  detect: null,
  fix: null,
  offline: true,
}

export const SAMPLE_BROKEN: PipelineState = {
  busy: null,
  field: "email_address",
  app: "client crashed: KeyError('email')",
  no_pr: false,
  detect: {
    ok: true,
    out: "",
    summary: { breaking: 1, warning: 0, info: 0, errors: 0 },
    status: ["breaking"],
    changes: [
      {
        severity: "breaking",
        location: "GET /v1/users/{id} response 200[application/json].email",
        message: "Property 'email' was removed (renamed to 'email_address').",
      },
    ],
  },
  fix: {
    ok: true,
    out: "",
    none: false,
    changes: ['Field User.email was renamed to "email_address".'],
    model: "nebius/Qwen/Qwen2.5-Coder-32B-Instruct",
    summary: "Update the client to read email_address instead of email.",
    files: "demo_repo/client.py",
    checks: "pytest passed",
    pr: "https://github.com/example/self-maintaining-api/pull/1",
    patch: `--- a/demo_repo/client.py
+++ b/demo_repo/client.py
@@ -8,7 +8,7 @@
 def user_email(user):
-    return user["email"]
+    return user["email_address"]
`,
  },
  offline: true,
}
