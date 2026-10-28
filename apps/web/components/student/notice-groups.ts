import { t } from "@/lib/copy";
import { joinWords } from "@/lib/format";
import type { NoticeChannel, NoticeResponse, StudentEnrolment, StudentNotice } from "@/lib/types";

/** One claim (enrolment), however many channels it was sent by; the list shows one block per claim (W3-2). */
export interface NoticeGroup {
  enrolmentId: string;
  institutionName: string;
  programmeName: string;
  programmeShort: string;
  academicYear: string;
  channels: NoticeChannel[];
  sentAt: string | null;
  expiresAt: string;
  reply: NoticeResponse | "NONE" | "EXPIRED";
  respondedAt: string | null;
  changedAt: string | null;
  /** Unanswered and still open: the student can reply from the link they were sent. */
  live: boolean;
}

/** A3.1: the first word and the code when the first word has a full stop ("B.Tech CSE"), else the name. */
export function programmeShort(name: string, code: string | null | undefined): string {
  const first = name.split(" ")[0] ?? "";
  return first.includes(".") && code ? `${first} ${code}` : name;
}

/** "email", "DigiLocker" or "email and DigiLocker" for notices.channels. */
export function channelWords(channels: NoticeChannel[]): string {
  const words = (["EMAIL", "DIGILOCKER"] as const).filter((c) => channels.includes(c)).map((c) => (c === "EMAIL" ? "email" : "DigiLocker"));
  return joinWords(words);
}

/**
 * Groups the student's notices by claim, newest first. A No on any channel
 * beats a Yes (D24); otherwise a Yes; an unanswered claim is EXPIRED only
 * when none of its notices is still open.
 */
export function groupNotices(notices: StudentNotice[], enrolments: StudentEnrolment[], now: number): NoticeGroup[] {
  const byClaim = new Map<string, StudentNotice[]>();
  for (const n of notices) byClaim.set(n.enrolment_id, [...(byClaim.get(n.enrolment_id) ?? []), n]);
  const groups: NoticeGroup[] = [];
  for (const [enrolmentId, list] of byClaim) {
    const first = list[0];
    const answered = list.filter((n) => n.response);
    const decisive = answered.find((n) => n.response === "NO") ?? answered.find((n) => n.response === "YES") ?? null;
    const open = list.filter((n) => !n.response && n.state !== "FAILED" && Date.parse(n.expires_at) > now);
    const reply: NoticeGroup["reply"] = decisive ? decisive.response! : open.length ? "NONE" : list.some((n) => n.state === "EXPIRED") ? "EXPIRED" : "NONE";
    const sent = list.map((n) => n.sent_at).filter((s): s is string => Boolean(s)).sort();
    const enrolment = enrolments.find((e) => e.id === enrolmentId);
    groups.push({
      enrolmentId,
      institutionName: first.institution_name,
      programmeName: first.programme_name,
      programmeShort: programmeShort(first.programme_name, enrolment?.programme_code),
      academicYear: first.academic_year,
      channels: [...new Set(list.map((n) => n.channel))],
      sentAt: sent[0] ?? null,
      expiresAt: (open[0] ?? first).expires_at,
      reply,
      respondedAt: decisive?.responded_at ?? null,
      changedAt: decisive?.changed_at ?? null,
      live: !decisive && open.length > 0,
    });
  }
  return groups.sort((a, b) => (b.sentAt ?? "").localeCompare(a.sentAt ?? ""));
}

/** The line under the strip on /student, by the claim's notices (deck section 8). Null after a Yes. */
export function homeLine(group: NoticeGroup | undefined, formatDate: (v: string | null) => string): string | null {
  if (!group) return t("student.check_student_pending");
  if (group.reply === "YES") return null;
  if (group.reply === "NO") return t("student.check_student_denied");
  if (group.reply === "EXPIRED") return t("student.check_student_expired");
  return t("student.check_student_sent", { sent_date: formatDate(group.sentAt) });
}
