import { requireRole } from "@/lib/auth";
import { AppShell } from "@/components/shell/app-shell";

export default async function UniversityLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("UNIVERSITY", "/university");
  return (
    <AppShell role="UNIVERSITY" user={user}>
      {children}
    </AppShell>
  );
}
