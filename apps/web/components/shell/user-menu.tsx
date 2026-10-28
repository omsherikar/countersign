"use client";

import { ChevronDown, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { t } from "@/lib/copy";
import { useLogout } from "@/lib/queries";
import { roleWord } from "@/lib/roles";
import type { User } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function shortName(user: User): string {
  if (user.role === "STUDENT") return user.name.split(" ")[0];
  if (user.role === "INSTITUTION") return "Registrar";
  if (user.role === "UNIVERSITY") return "COE";
  if (user.role === "RO_OFFICER") return "RO";
  return "Admin";
}

export function UserMenu({ user }: { user: User }) {
  const router = useRouter();
  const logout = useLogout();
  const signOut = () =>
    logout.mutate(undefined, {
      onSettled: () => {
        router.replace("/login?signed_out=1");
        router.refresh();
      },
    });
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="h-9 gap-1.5 px-2.5 text-sm font-medium">
          <span className="max-w-32 truncate">{shortName(user)}</span>
          <ChevronDown className="size-4 text-ink-muted" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="flex flex-col gap-0.5 font-normal">
          <span className="truncate text-sm font-medium text-ink">{user.name}</span>
          <span className="truncate text-xs text-ink-muted">{roleWord(user)}</span>
          <span className="truncate text-xs text-ink-faint">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut} disabled={logout.isPending}>
          <LogOut className="size-4" aria-hidden="true" />
          {t("shell.signout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
