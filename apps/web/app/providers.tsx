"use client";

import { QueryProvider } from "@/components/query-provider";

export function Providers({ children }: { children: React.ReactNode }) {
  return <QueryProvider>{children}</QueryProvider>;
}
