import { Gavel } from "lucide-react";
import { t, tk } from "@/lib/copy";
import type { StudentEnrolment } from "@/lib/types";

/**
 * After an officer decides the student's dispute, the student reads the
 * outcome in plain words, with the reason for an upheld claim, never the
 * officer's note or name (copy deck section 23, student.decision.*).
 */
export function DecisionLine({ enrolment, className }: { enrolment: Pick<StudentEnrolment, "decision" | "institution_name">; className?: string }) {
  const d = enrolment.decision;
  if (!d) return null;
  const reason = d.reason_code ? tk(`reason.UPHOLD.${d.reason_code}`) : "";
  return (
    <p className={className ?? "mt-2 flex max-w-[68ch] items-start gap-2 border-l-2 border-rule-strong bg-paper-raised px-3 py-2 text-md"}>
      <Gavel className="mt-1 size-4 shrink-0 text-ink-muted" aria-hidden="true" />
      <span>{t(`student.decision.${d.outcome}`, { institution_name: enrolment.institution_name, reason_word: reason })}</span>
    </p>
  );
}
