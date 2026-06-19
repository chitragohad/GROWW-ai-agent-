import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    PULSE_API_URL: process.env.PULSE_API_URL ?? "http://127.0.0.1:8001",
  },
  async rewrites() {
    const apiUrl = process.env.PULSE_API_URL ?? "http://127.0.0.1:8001";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
