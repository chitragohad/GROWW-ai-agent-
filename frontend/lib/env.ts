/** Deployment environment helpers for the Next.js dashboard. */

export function isVercelDeploy(): boolean {
  return process.env.VERCEL === "1";
}

export function isProductionDeploy(): boolean {
  return isVercelDeploy() || process.env.PULSE_ENV === "production";
}

export function apiBaseUrl(): string {
  return process.env.PULSE_API_URL ?? "http://127.0.0.1:8001";
}
