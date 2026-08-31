"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session, getSession } from "@/lib/api";
import Sidebar from "./Sidebar";

export default function AuthShell({
  title,
  eyebrow,
  action,
  children,
}: {
  title: string;
  eyebrow?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null | "loading">("loading");

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/");
      return;
    }
    setSession(s);
  }, [router]);

  if (session === "loading" || session === null) {
    return <div className="min-h-screen bg-bpr-parchment" />;
  }

  return (
    <div className="flex min-h-screen bg-bpr-parchment">
      <Sidebar session={session} />
      <div className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-bpr-hairline bg-bpr-parchment/90 px-8 py-5 backdrop-blur">
          <div>
            {eyebrow && (
              <p className="mb-1 text-[11px] font-medium uppercase tracking-[0.16em] text-bpr-ink2/60">{eyebrow}</p>
            )}
            <h1 className="font-display text-[26px] font-medium leading-none text-bpr-navy">{title}</h1>
          </div>
          {action}
        </header>
        <main className="animate-rise px-8 py-7">{children}</main>
      </div>
    </div>
  );
}
