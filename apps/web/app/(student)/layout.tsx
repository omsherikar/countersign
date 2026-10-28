import { requireRole } from "@/lib/auth";
import { AppShell } from "@/components/shell/app-shell";

export default async function StudentLayout({ children }: { children: React.ReactNode }) {
  const user = await requireRole("STUDENT", "/student");
  return (
    <AppShell role="STUDENT" user={user}>
      {children}
    </AppShell>
  );
}
