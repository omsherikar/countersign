import type { Metadata } from "next";
import { ColumnMappingPage } from "@/components/uploads/column-mapping-page";

export const metadata: Metadata = { title: "Column mapping" };

export default function CollegeColumnMapping() {
  return <ColumnMappingPage />;
}
