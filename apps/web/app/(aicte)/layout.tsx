import { requireRole } from "@/lib/auth";
import { AppShell } from "@/components/shell/app-shell";

export default async function AicteLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("AICTE_ADMIN", "/aicte");
  return (
    <AppShell role="AICTE_ADMIN" user={user}>
      {children}
    </AppShell>
  );
}
