import { NextResponse } from "next/server";

const DEFAULT_BACKEND_URL = "http://localhost:9001";

function getBackendBaseUrl(): string {
  const candidate =
    process.env.KG_BACKEND_URL ||
    process.env.NEXT_PUBLIC_KG_BACKEND_URL ||
    DEFAULT_BACKEND_URL;
  const url = candidate.replace(/\/+$/, "");
  console.log(`[Backend Proxy] Using backend URL: ${url}`);
  return url;
}

export async function proxyRequest(path: string, init: RequestInit = {}): Promise<NextResponse> {
  const target = `${getBackendBaseUrl()}${path}`;
  console.log(`[Backend Proxy] Proxying request to: ${target}`);

  try {
    const headers = new Headers(init.headers);
    const response = await fetch(target, {
      ...init,
      headers,
      cache: "no-store",
    });

    const body = await response.text();
    const contentType = response.headers.get("content-type") || "application/json";
    
    console.log(`[Backend Proxy] Response status: ${response.status}, type: ${contentType}`);

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": contentType,
      },
    });
  } catch (error) {
    console.error(`[Backend Proxy] Error: ${error instanceof Error ? error.message : String(error)}`);
    return NextResponse.json(
      {
        ok: false,
        error: "KubeGuard backend unavailable",
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 502 },
    );
  }
}
