"use client";

import { useQuery } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { api } from "@/lib/api";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const query = useQuery({
    queryKey: ["auth", "me"],
    queryFn: api.me,
    retry: false,
  });

  useEffect(() => {
    if (query.isError && pathname !== "/login") {
      router.replace("/login");
    }
  }, [pathname, query.isError, router]);

  if (query.isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-slate-500">
        正在验证管理员身份...
      </div>
    );
  }

  if (query.isError) {
    return null;
  }

  return <>{children}</>;
}
