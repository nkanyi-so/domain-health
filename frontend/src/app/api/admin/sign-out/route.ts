import { clearAdminSession, crossSite, json } from "@/lib/server/routes";

export async function POST(request: Request): Promise<Response> {
  const refused = crossSite(request);
  if (refused) {
    return refused;
  }
  await clearAdminSession();
  return json(200, { ok: true });
}
