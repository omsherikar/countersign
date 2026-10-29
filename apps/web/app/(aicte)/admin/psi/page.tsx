import type { Metadata } from "next";
import { PsiPage } from "@/components/admin/psi-page";

export const metadata: Metadata = { title: "Private matching" };

export default function AdminPsi() {
  return <PsiPage />;
}
