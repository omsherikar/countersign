import Link from "next/link";
import { t, tk } from "@/lib/copy";
import { formatCount, formatDate } from "@/lib/format";
import type { LastUpload } from "@/lib/types";

/** "Last upload 28 Oct 2026: 605 rows, 0 with errors · Done", linked to the batch page when there is one for this role. */
export function LastUploadLine({ last, href, className }: { last: LastUpload | null; href?: (batchId: string) => string; className?: string }) {
  if (!last) return <p className={className}>{t("college.no_upload_yet")}</p>;
  const text = t("last_upload.line", {
    uploaded_date: formatDate(last.uploaded_at),
    rows: formatCount(last.rows),
    errors: formatCount(last.errors),
    status_word: tk(`upload_status.${last.status}`),
  });
  return <p className={className}>{href ? <Link href={href(last.batch_id)}>{text}</Link> : text}</p>;
}
