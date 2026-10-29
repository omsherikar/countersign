import type { Metadata } from "next";
import { Suspense } from "react";
import { DigiLockerReturn } from "@/components/auth/digilocker-return";

export const metadata: Metadata = { title: "Signing in", robots: { index: false, follow: false }, referrer: "no-referrer" };

/** Where every DigiLocker sign-in lands (API_CONTRACT A4.12); public, no shell. */
export default function DigiLockerReturnPage() {
  return (
    <Suspense>
      <DigiLockerReturn />
    </Suspense>
  );
}
