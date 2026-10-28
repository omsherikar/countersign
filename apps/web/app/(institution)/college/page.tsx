import type { Metadata } from "next";
import { CollegeLedger } from "@/components/college/college-ledger";

export const metadata: Metadata = { title: "Seat ledger" };

export default function CollegePage() {
  return <CollegeLedger />;
}
