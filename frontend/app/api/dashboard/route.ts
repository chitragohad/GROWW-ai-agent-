import { NextResponse } from "next/server";

import { loadDashboardData } from "@/lib/dashboard-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const data = await loadDashboardData();
  return NextResponse.json(data);
}
