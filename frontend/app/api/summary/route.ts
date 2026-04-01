import { proxyRequest } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
  return proxyRequest("/api/summary");
}
