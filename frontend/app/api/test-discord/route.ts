import { proxyRequest } from "@/lib/backend";

export const dynamic = "force-dynamic";

export async function POST() {
  return proxyRequest("/api/integrations/test-discord", { method: "POST" });
}
