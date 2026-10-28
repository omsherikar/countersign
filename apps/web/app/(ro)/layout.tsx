import { requireRole } from "@/lib/auth";
import { AppShell } from "@/components/shell/app-shell";

export default async function RegionalLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("RO_OFFICER", "/ro");
  return (
    <AppShell role="RO_OFFICER" user={user}>
      {children}
    </AppShell>
  );
}
