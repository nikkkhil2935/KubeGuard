import { proxyRequest } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  return proxyRequest("/api/actions/crash", { method: "POST" });
}
