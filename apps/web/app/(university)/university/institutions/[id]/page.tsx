import type { Metadata } from "next";
import { Suspense } from "react";
import { t } from "@/lib/copy";
import { InstitutionDetail } from "@/components/institution/institution-detail";

export const metadata: Metadata = { title: "Institution" };

export default async function UniversityInstitution({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <InstitutionDetail id={id} crumbRoot={{ label: t("nav.affiliated"), href: "/university" }} showFlags={false} />
    </Suspense>
  );
}
