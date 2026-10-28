import type { Metadata } from "next";
import { Suspense } from "react";
import { t } from "@/lib/copy";
import { DegreesPage } from "@/components/university/degrees-page";

export const metadata: Metadata = { title: t("degree.heading") };

export default function Degrees() {
  return (
    <Suspense>
      <DegreesPage />
    </Suspense>
  );
}
