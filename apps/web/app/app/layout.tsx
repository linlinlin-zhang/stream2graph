import { AuthGate } from "@/components/auth-gate";
import { AdminShell } from "@/components/admin-shell";

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <AdminShell>{children}</AdminShell>
    </AuthGate>
  );
}
