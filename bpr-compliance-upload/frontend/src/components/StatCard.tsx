import type { LucideIcon } from "lucide-react";
import Card from "./Card";

export default function StatCard({
  label,
  value,
  icon: Icon,
  tone = "default",
  hint,
}: {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: "default" | "brass" | "rose";
  hint?: string;
}) {
  const iconTone =
    tone === "brass" ? "bg-bpr-brass/12 text-[#8C6420]" : tone === "rose" ? "bg-bpr-rose/12 text-bpr-rose" : "bg-bpr-navy/8 text-bpr-navy";

  return (
    <Card className="flex items-start justify-between">
      <div>
        <p className="text-[12px] font-medium uppercase tracking-wide text-bpr-ink2/60">{label}</p>
        <p className="mt-2 font-display text-[32px] leading-none text-bpr-navy">{value}</p>
        {hint && <p className="mt-1.5 text-[12px] text-bpr-ink2/60">{hint}</p>}
      </div>
      <div className={`rounded-lg p-2.5 ${iconTone}`}>
        <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
      </div>
    </Card>
  );
}
