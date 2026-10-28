import type { Metadata } from "next";
import { StudentHome } from "@/components/student/student-home";

export const metadata: Metadata = { title: "My enrolment" };

export default function StudentPage() {
  return <StudentHome />;
}
