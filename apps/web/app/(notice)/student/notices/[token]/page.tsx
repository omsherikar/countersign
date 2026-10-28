import type { Metadata } from "next";
import { NoticePage } from "@/components/student/notice-page";

/**
 * The public notice link (W3-1). It sits outside the (student) group so it
 * renders with no session, no nav and no role guard; the token is the key.
 * No referrer leaves the page, so the token never reaches another site.
 */
export const metadata: Metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default async function Notice({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <NoticePage token={token} />;
}
