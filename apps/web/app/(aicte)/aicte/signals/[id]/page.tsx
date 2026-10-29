import type { Metadata } from "next";
import { SignalDetailPage } from "@/components/signals/signal-detail";

export const metadata: Metadata = { title: "Signal" };

export default async function Signal({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SignalDetailPage id={id} variant="aicte" />;
}
