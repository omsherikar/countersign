import type { Metadata } from "next";
import { Suspense } from "react";
import { ClaimPage } from "@/components/student/claim-page";

/**
 * /student/claim (W4-9): a DigiLocker identity without an APAAR links itself
 * to the record its college made, with the provisional ID. It runs on the
 * pending claim the sign-in left, before any session exists, so it sits
 * outside the (student) group and the proxy lets it through.
 */
export const metadata: Metadata = { title: "Claim your record", robots: { index: false, follow: false }, referrer: "no-referrer" };

const DEMO = process.env.DEMO_MODE === "true" || process.env.NEXT_PUBLIC_MOCK_API === "1";

export default function Claim() {
  return (
    <Suspense>
      <ClaimPage demo={DEMO} />
    </Suspense>
  );
}
