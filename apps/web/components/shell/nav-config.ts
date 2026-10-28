import {
  Bell,
  BookOpen,
  FileChartColumn,
  Flag,
  Gauge,
  Inbox,
  LayoutDashboard,
  Landmark,
  Lock,
  Printer,
  ScrollText,
  Server,
  Shield,
  Upload,
  UserRound,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { CopyId } from "@/lib/copy";
import type { Role } from "@/lib/types";

export interface NavItem {
  label: CopyId;
  href: string;
  icon: LucideIcon;
  /** Week the endpoints behind this item arrive (ARCHITECTURE section 10). Items after Week 1 never navigate. */
  week: 1 | 2 | 3 | 4;
  /** Match only the exact path (landing pages), not children. */
  exact?: boolean;
  /** Extra prefixes that also mark this item active (detail pages under the landing route). */
  alsoActive?: string[];
}

export const NAV: Record<Exclude<Role, "VERIFIER">, NavItem[]> = {
  AICTE_ADMIN: [
    { label: "nav.overview", href: "/aicte", icon: LayoutDashboard, week: 1, alsoActive: ["/aicte/institutions"] },
    { label: "nav.cases", href: "/aicte/cases", icon: Inbox, week: 2 },
    { label: "nav.reports", href: "/aicte/reports", icon: FileChartColumn, week: 4 },
    { label: "nav.system", href: "/admin/system", icon: Server, week: 1 },
    { label: "nav.audit", href: "/admin/audit", icon: ScrollText, week: 3 },
    { label: "nav.psi", href: "/admin/psi", icon: Lock, week: 4 },
  ],
  RO_OFFICER: [
    { label: "nav.overview", href: "/ro", icon: LayoutDashboard, week: 1, alsoActive: ["/ro/institutions"] },
    { label: "nav.cases", href: "/ro/cases", icon: Inbox, week: 2 },
    { label: "nav.reports", href: "/ro/reports", icon: FileChartColumn, week: 4 },
  ],
  INSTITUTION: [
    { label: "nav.ledger", href: "/college", icon: BookOpen, week: 1, exact: true },
    { label: "nav.upload", href: "/college/upload", icon: Upload, week: 2 },
    { label: "nav.enrolments", href: "/college/enrolments", icon: Users, week: 1 },
    { label: "nav.flags", href: "/college/flags", icon: Flag, week: 2 },
    { label: "nav.score", href: "/college/score", icon: Gauge, week: 4 },
  ],
  STUDENT: [
    { label: "nav.my_enrolment", href: "/student", icon: UserRound, week: 1, exact: true },
    { label: "nav.notices", href: "/student/notices", icon: Bell, week: 3 },
    { label: "nav.wallet", href: "/student/wallet", icon: Wallet, week: 3 },
    { label: "nav.privacy", href: "/student/privacy", icon: Shield, week: 3 },
  ],
  UNIVERSITY: [
    { label: "nav.affiliated", href: "/university", icon: Landmark, week: 1, alsoActive: ["/university/institutions"] },
    { label: "nav.degree_print", href: "/university/degrees", icon: Printer, week: 3 },
  ],
};

export function isActive(item: NavItem, pathname: string): boolean {
  if (pathname === item.href) return true;
  if (item.alsoActive?.some((p) => pathname.startsWith(p))) return true;
  if (item.exact) return false;
  return pathname.startsWith(`${item.href}/`);
}
