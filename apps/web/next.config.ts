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
  /**
   * The browser only calls /api on its own origin. The rewrite proxies each
   * call to the api as it is and never follows a redirect: the 302s of
   * /api/auth/digilocker/start and /callback reach the browser with their
   * Location and every Set-Cookie unchanged (API_CONTRACT A4.1), so the
   * DigiLocker sign-in round trip works through the same origin.
   */
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/:path*` }];
  },
  /** Old paths keep working for links already sent or printed (W4 changes to earlier pages). */
  async redirects() {
    return [
      { source: "/college/flags", destination: "/college/cases", permanent: true },
      { source: "/college/flags/:caseId", destination: "/college/cases/:caseId", permanent: true },
      { source: "/university/degrees", destination: "/university/certificates", permanent: true },
      { source: "/university/degrees/:enrolmentId/print", destination: "/university/certificates/:enrolmentId/print", permanent: true },
      { source: "/verify/degree/:shortId", destination: "/verify/completion/:shortId", permanent: true },
    ];
  },
};

export default nextConfig;
