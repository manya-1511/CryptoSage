import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";

const API_BASE = process.env.API_URL || "http://localhost:8000";

/**
 * Server-side proxy to POST /explain/{firmwareId} on the CryptoSage
 * FastAPI backend. Kept server-side (using API_URL, not
 * NEXT_PUBLIC_API_BASE_URL) so the backend's network location never
 * has to be exposed to the browser, and so this route can enforce
 * that only signed-in users can trigger analysis.
 */
export async function POST(req: Request) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { firmwareId } = await req.json();

  if (!firmwareId) {
    return NextResponse.json({ error: "firmwareId is required" }, { status: 400 });
  }

  try {
    const res = await fetch(`${API_BASE}/explain/${firmwareId}`, { method: "POST" });

    if (!res.ok) {
      const errorBody = await res.json().catch(() => null);
      return NextResponse.json(
        {
          error:
            errorBody?.detail?.message || errorBody?.detail || "Failed to generate explanation.",
        },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Could not reach the analysis backend." }, { status: 502 });
  }
}
