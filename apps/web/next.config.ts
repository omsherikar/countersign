import type { NextConfig } from "next";

const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not write AGENTS.md into the app on `next dev`.
  agentRules: false,
  // Keep the dev badge out of demo screens and screenshots.
  devIndicators: false,
  experimental: {
    // Verifying the audit chain walks every entry; under load that can pass the default 30 s.
    proxyTimeout: 120_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/:path*` }];
  },
};

export default nextConfig;
