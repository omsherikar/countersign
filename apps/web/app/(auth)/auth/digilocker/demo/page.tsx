import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { MOCK_API } from "@/lib/api";
import { t } from "@/lib/copy";
import { DemoDigiLocker } from "@/components/auth/demo-digilocker";

export const metadata: Metadata = { title: t("dldemo.title"), robots: { index: false, follow: false } };

/**
 * Stands in for mockgov's Demo DigiLocker (API_CONTRACT A4.25 C.11) when the
 * web runs on the mock api, so the sign-in round trip can be walked without
 * the backend. Against the api it does not exist: sign-in goes to mockgov.
 */
export default function DemoDigiLockerPage() {
  if (!MOCK_API) notFound();
  return (
    <Suspense>
      <DemoDigiLocker />
    </Suspense>
  );
}
