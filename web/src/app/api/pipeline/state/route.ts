import { NextResponse } from "next/server"
import { OFFLINE_STATE } from "@/lib/pipeline"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const res = await fetch("http://127.0.0.1:8001/state", {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    })
    if (!res.ok) {
      return NextResponse.json({ ...OFFLINE_STATE, offline: true })
    }
    const data = await res.json()
    return NextResponse.json({ ...data, offline: false })
  } catch {
    return NextResponse.json({ ...OFFLINE_STATE, offline: true })
  }
}
