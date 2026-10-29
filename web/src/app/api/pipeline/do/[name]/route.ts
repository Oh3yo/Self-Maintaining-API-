import { NextResponse } from "next/server"

export const dynamic = "force-dynamic"

const ACTIONS = new Set(["break", "reset", "detect", "fix", "restart"])

export async function POST(
  _request: Request,
  context: { params: Promise<{ name: string }> }
) {
  const { name } = await context.params
  if (!ACTIONS.has(name)) {
    return NextResponse.json({ error: "unknown action" }, { status: 400 })
  }
  try {
    const res = await fetch(`http://127.0.0.1:8001/do/${name}`, {
      method: "POST",
      signal: AbortSignal.timeout(3000),
    })
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
    })
  } catch {
    return NextResponse.json(
      { error: "Live console is not running. Start it with python dashboard.py" },
      { status: 503 }
    )
  }
}
