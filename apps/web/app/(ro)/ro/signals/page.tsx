import type { Metadata } from "next";
import { Suspense } from "react";
import { SignalsPage } from "@/components/signals/signals-page";

export const metadata: Metadata = { title: "Signals" };

export default function Signals() {
  return (
    <Suspense>
      <SignalsPage variant="ro" />
    </Suspense>
  );
}
