import { redirect } from "next/navigation";

/** The approvals tab has its own URL in the sitemap; it opens the detail page on that tab. */
export default async function ApprovalsTab({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/aicte/institutions/${id}#approvals`);
}
