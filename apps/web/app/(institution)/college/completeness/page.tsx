import type { Metadata } from "next";
import { CollegeCompleteness } from "@/components/college/college-completeness";

export const metadata: Metadata = { title: "Completeness" };

export default function CollegeCompletenessPage() {
  return <CollegeCompleteness />;
}
