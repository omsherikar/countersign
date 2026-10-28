import { requireRole } from "@/lib/auth";
import { AppShell } from "@/components/shell/app-shell";

export default async function InstitutionLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("INSTITUTION", "/college");
  return (
    <AppShell role="INSTITUTION" user={user}>
      {children}
    </AppShell>
  );
}
