import { NextResponse } from "next/server";

const API_BASE = process.env.API_URL || "http://localhost:8000";

/** Lets the frontend's own health checks (e.g. Docker healthcheck) verify
 *  that the CryptoSage backend is reachable, without exposing its URL. */
export async function GET() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json({ frontend: "ok", backend: data }, { status: res.ok ? 200 : 502 });
  } catch {
    return NextResponse.json(
      { frontend: "ok", backend: { status: "unreachable" } },
      { status: 502 }
    );
  }
}
