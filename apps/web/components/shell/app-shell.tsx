"use client";

import * as React from "react";
import Link from "next/link";
import { Menu } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { t } from "@/lib/copy";
import { REGION_NAME, ROLE_PLURAL, ROLE_SINGULAR, landingFor, roleWord } from "@/lib/roles";
import type { Role, User } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useMe } from "@/components/providers/root-provider";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { InstitutionSearch } from "@/components/shell/institution-search";
import { Logo } from "@/components/shell/logo";
import { NAV } from "@/components/shell/nav-config";
import { NavList } from "@/components/shell/nav-list";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { UserMenu } from "@/components/shell/user-menu";

type ShellRole = Exclude<Role, "VERIFIER">;

/** Scope label for the top bar; matches dashboard.scope.label without another request. */
export function scopeLabel(user: User): string {
  switch (user.role) {
    case "AICTE_ADMIN":
      return "All India";
    case "RO_OFFICER":
      return user.scope.region ? `${REGION_NAME[user.scope.region]} Region` : "";
    case "INSTITUTION":
      return user.scope.institution_name ?? "";
    case "UNIVERSITY":
      return user.scope.university_name ?? "";
    default:
      return "";
  }
}

const SEARCH_BASE: Partial<Record<ShellRole, string>> = {
  AICTE_ADMIN: "/aicte",
  RO_OFFICER: "/ro",
  UNIVERSITY: "/university",
};

/** After a role-mismatch redirect, say why once and drop the query param. */
function DeniedNotice({ user }: { user: User }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const denied = params.get("denied") as Role | null;
  React.useEffect(() => {
    if (!denied || !(denied in ROLE_PLURAL)) return;
    toast(
      t("err.FORBIDDEN_redirect", {
        required_roles_words: ROLE_PLURAL[denied],
        role_word: ROLE_SINGULAR[user.role],
      }),
    );
    const rest = new URLSearchParams(params.toString());
    rest.delete("denied");
    const qs = rest.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [denied, params, pathname, router, user.role]);
  return null;
}

/**
 * One shell per role group: top bar with the wordmark, scope label and role
 * stamp, user menu and theme; a left nav on desktop and a sheet on phones.
 * Students get a single column with the nav as a row under the bar.
 */
export function AppShell({ role, user: serverUser, children }: { role: ShellRole; user: User; children: React.ReactNode }) {
  const { user: clientUser } = useMe();
  const user = clientUser && clientUser.role === serverUser.role ? clientUser : serverUser;
  const [open, setOpen] = React.useState(false);
  const items = NAV[role];
  const landing = landingFor(role);
  const searchBase = SEARCH_BASE[role];
  const scope = scopeLabel(user);
  const student = role === "STUDENT";

  return (
    <div className="min-h-dvh bg-paper">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-paper-raised focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <React.Suspense fallback={null}>
        <DeniedNotice user={user} />
      </React.Suspense>
      <header className="sticky top-0 z-40 border-b border-rule-strong bg-paper-raised">
        <div className="flex h-14 items-center gap-3 px-4 md:px-5">
          {!student && (
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
                  <Menu className="size-5" aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-72 bg-sidebar p-0">
                <SheetHeader className="border-b border-line px-4 py-3">
                  <SheetTitle className="font-sans text-sm font-semibold">{scope || t("brand.name")}</SheetTitle>
                  <SheetDescription className="text-xs">{roleWord(user)}</SheetDescription>
                </SheetHeader>
                <nav aria-label="Main" className="p-3">
                  <NavList items={items} onNavigate={() => setOpen(false)} />
                </nav>
              </SheetContent>
            </Sheet>
          )}
          <Link href={landing} className="flex shrink-0 items-center rounded-md no-underline" aria-label={`${t("brand.name")}, ${t(items[0].label)}`}>
            <Logo className="h-7" />
          </Link>
          {scope && (
            <div className="hidden min-w-0 items-center gap-3 border-l border-line pl-3 lg:flex">
              <span className="truncate text-sm font-medium text-ink" title={scope}>
                {scope}
              </span>
            </div>
          )}
          <span className="stamp stamp--blue hidden shrink-0 sm:inline-flex" title={roleWord(user)}>
            {roleWord(user)}
          </span>
          <div className="flex-1" />
          {searchBase && (
            <div className="hidden flex-1 justify-end md:flex">
              <InstitutionSearch basePath={searchBase} />
            </div>
          )}
          <ThemeToggle />
          <UserMenu user={user} />
        </div>
        {student && (
          <nav aria-label="Main" className="mx-auto max-w-[640px] px-4 pb-2">
            <NavList items={items} orientation="horizontal" />
          </nav>
        )}
      </header>
      <div className="flex">
        {!student && (
          <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-[220px] shrink-0 overflow-y-auto border-r border-line bg-sidebar md:block">
            <nav aria-label="Main" className="p-3">
              <NavList items={items} />
            </nav>
          </aside>
        )}
        <main
          id="main"
          className={cn("min-w-0 flex-1 px-4 pt-6 pb-16 md:px-6", student ? "mx-auto max-w-[640px] md:px-4" : "max-w-[1328px]")}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
