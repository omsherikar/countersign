import { test as setup, expect } from "@playwright/test";
import { API_URL, MAILPIT_URL, MOCKGOV_URL, ROLES, WEB_URL, signIn, type Role } from "./support";

setup("the stack answers", async ({ request }) => {
  const checks: [string, string][] = [
    ["web", `${WEB_URL}/login`],
    ["api", `${API_URL}/healthz`],
    ["mockgov", `${MOCKGOV_URL}/healthz`],
    ["Mailpit", `${MAILPIT_URL}/api/v1/messages?limit=1`],
  ];
  for (const [name, url] of checks) {
    // The web runs `next dev`, which compiles a route on its first visit.
    const res = await request.get(url, { failOnStatusCode: false, timeout: 120_000 }).catch(() => null);
    expect(res?.ok(), `${name} does not answer at ${url}; start it with make up, then seed it with make demo-reset`).toBeTruthy();
  }
});

// Officers, the registrar and the university sign in with a password; students only ever sign in through DigiLocker.
for (const role of Object.keys(ROLES) as Role[]) {
  setup(`sign in as ${ROLES[role].email}`, async () => {
    await signIn(role);
  });
}
