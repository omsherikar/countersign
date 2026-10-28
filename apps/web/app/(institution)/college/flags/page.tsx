import type { Metadata } from "next";
import { Suspense } from "react";
import { CasesPage } from "@/components/flags/cases-page";

export const metadata: Metadata = { title: "Flags" };

export default function CollegeFlags() {
  return (
    <Suspense>
      <CasesPage variant="college" />
    </Suspense>
  );
}
