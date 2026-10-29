import { redirect } from "next/navigation";

/** The completeness tab has its own URL in the sitemap; it opens the detail page on that tab. */
export default async function CompletenessTab({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/ro/institutions/${id}#completeness`);
}
