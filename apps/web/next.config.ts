import type { NextConfig } from "next";

const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not write AGENTS.md into the app on `next dev`.
  agentRules: false,
  // Keep the dev badge out of demo screens and screenshots.
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/:path*` }];
  },
};

export default nextConfig;
