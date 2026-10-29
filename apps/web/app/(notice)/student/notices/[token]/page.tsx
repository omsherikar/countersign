import type { Metadata } from "next";
import { NoticePage } from "@/components/student/notice-page";

/**
 * The public notice link (W3-1, W4-8). It sits outside the (student) group
 * so it renders with no session, no nav and no role guard; the token shows
 * the claim, and answering needs DigiLocker sign-in. No referrer leaves the
 * page, so the token never reaches another site.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

/** The demo note under the sign-in button shows only in the demo (DEMO_MODE) and with the mock api. */
const DEMO = process.env.DEMO_MODE === "true" || process.env.NEXT_PUBLIC_MOCK_API === "1";

export default async function Notice({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <NoticePage token={token} demo={DEMO} />;
}
