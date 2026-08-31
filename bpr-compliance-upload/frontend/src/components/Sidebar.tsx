"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShieldAlert,
  FileText,
  Landmark,
  ScrollText,
  LogOut,
  Stamp,
  BrainCircuit,
  type LucideIcon,
} from "lucide-react";
import { Session, clearSession } from "@/lib/api";

const NAV_ITEMS: { href: string; label: string; icon: LucideIcon; roles: Session["role"][] }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["loan_officer", "compliance_officer", "auditor"] },
  { href: "/screening", label: "Screening Queue", icon: ShieldAlert, roles: ["compliance_officer", "auditor"] },
  { href: "/analysis", label: "Compliance Analysis", icon: BrainCircuit, roles: ["compliance_officer", "auditor"] },
  { href: "/reports", label: "Report Editor", icon: FileText, roles: ["compliance_officer"] },
  { href: "/loan-decisions", label: "Loan Decisions", icon: Landmark, roles: ["loan_officer"] },
  { href: "/audit", label: "Audit Explorer", icon: ScrollText, roles: ["auditor"] },
];

const ROLE_LABEL: Record<Session["role"], string> = {
  loan_officer: "Loan Officer",
  compliance_officer: "Compliance Officer",
  auditor: "Auditor",
};

export default function Sidebar({ session }: { session: Session }) {
  const pathname = usePathname();
  const router = useRouter();
  const items = NAV_ITEMS.filter((i) => i.roles.includes(session.role));

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-bpr-ink text-bpr-parchment">
      <div className="flex items-center gap-2 px-5 py-6">
        <Stamp className="h-5 w-5 text-bpr-brassLight" strokeWidth={1.75} />
        <div className="font-display text-[15px] leading-tight tracking-wide">
          BPR Compliance
          <div className="text-[10px] font-sans uppercase tracking-[0.18em] text-bpr-parchment/50">Copilot</div>
        </div>
      </div>

      <nav className="mt-2 flex-1 space-y-0.5 px-3">
        {items.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center gap-3 rounded-md px-3 py-2 text-[13.5px] transition-colors ${
                active
                  ? "bg-white/[0.07] text-bpr-brassLight"
                  : "text-bpr-parchment/70 hover:bg-white/[0.04] hover:text-bpr-parchment"
              }`}
            >
              <Icon className="h-[17px] w-[17px]" strokeWidth={1.75} />
              {item.label}
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-bpr-brassLight" />}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="mb-3 rounded-lg bg-white/[0.04] px-3 py-2.5">
          <p className="truncate text-[13px] font-medium text-bpr-parchment">{session.name}</p>
          <p className="text-[11px] uppercase tracking-wide text-bpr-parchment/50">{ROLE_LABEL[session.role]}</p>
        </div>
        <button
          onClick={() => {
            clearSession();
            router.push("/");
          }}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-[13px] text-bpr-parchment/60 transition-colors hover:bg-white/[0.05] hover:text-bpr-parchment"
        >
          <LogOut className="h-4 w-4" strokeWidth={1.75} />
          Log out
        </button>
      </div>
    </aside>
  );
}
