import type { Metadata } from "next";
import { Suspense } from "react";
import { CollegeEnrolments } from "@/components/college/college-enrolments";

export const metadata: Metadata = { title: "Enrolments" };

export default function CollegeEnrolmentsPage() {
  return (
    <Suspense>
      <CollegeEnrolments />
    </Suspense>
  );
}
