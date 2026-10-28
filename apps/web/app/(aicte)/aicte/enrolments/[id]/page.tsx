import type { Metadata } from "next";
import { Suspense } from "react";
import { EnrolmentDetail } from "@/components/enrolment/enrolment-detail";

export const metadata: Metadata = { title: "Enrolment" };

export default async function Enrolment({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <EnrolmentDetail id={id} variant="aicte" />
    </Suspense>
  );
}
