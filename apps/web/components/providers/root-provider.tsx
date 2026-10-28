"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { ThemeProvider } from "next-themes";
import { ApiError } from "@/lib/api";
import { useMeQuery } from "@/lib/queries";
import { roleForPath } from "@/lib/roles";
import type { User } from "@/lib/types";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

function makeClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (count, err) => {
          // Envelope answers (401, 403, 404, 422) are final; retry only flaky ones.
          if (err instanceof ApiError && err.status > 0 && err.status < 500) return false;
          return count < 1;
        },
      },
    },
  });
}

interface MeContextValue {
  user: User | null;
  isLoading: boolean;
}

const MeContext = React.createContext<MeContextValue>({ user: null, isLoading: true });

function MeProvider({ initialUser, children }: { initialUser: User | null; children: React.ReactNode }) {
  // Public pages (/login, /verify) never ask who is signed in.
  const onRoleRoute = roleForPath(usePathname() ?? "/") !== null;
  const query = useMeQuery(onRoleRoute);
  const user = query.data === undefined ? initialUser : query.data;
  const value = React.useMemo<MeContextValue>(
    () => ({ user, isLoading: onRoleRoute && query.isLoading && initialUser === null }),
    [user, onRoleRoute, query.isLoading, initialUser],
  );
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>;
}

/** The signed-in user, from one GET /me per page load. */
export function useMe(): MeContextValue {
  return React.useContext(MeContext);
}

/**
 * Theme, query cache, tooltips, toasts and the session. `initialUser` comes
 * from the server layout so the shell paints with the right name at once;
 * the client still calls GET /me once to keep the cache honest.
 */
export function RootProvider({ initialUser = null, children }: { initialUser?: User | null; children: React.ReactNode }) {
  const [client] = React.useState(makeClient);
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={client}>
        <TooltipProvider delayDuration={200}>
          <MeProvider initialUser={initialUser}>{children}</MeProvider>
          <Toaster position="bottom-right" />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
