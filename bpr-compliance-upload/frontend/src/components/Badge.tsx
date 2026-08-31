export type BadgeTone = "brass" | "teal" | "rose" | "plum" | "neutral";

const TONE_CLASSES: Record<BadgeTone, string> = {
  brass: "bg-bpr-brass/12 text-[#8C6420] ring-1 ring-inset ring-bpr-brass/25",
  teal: "bg-bpr-teal/12 text-bpr-teal ring-1 ring-inset ring-bpr-teal/25",
  rose: "bg-bpr-rose/12 text-bpr-rose ring-1 ring-inset ring-bpr-rose/25",
  plum: "bg-bpr-plum/12 text-bpr-plum ring-1 ring-inset ring-bpr-plum/25",
  neutral: "bg-bpr-ink2/10 text-bpr-ink2 ring-1 ring-inset ring-bpr-ink2/20",
};

export const FLAG_STATUS_TONE: Record<string, BadgeTone> = {
  open: "brass",
  accepted: "teal",
  approved: "teal",
  rejected: "neutral",
  escalated: "plum",
};

export default function Badge({ tone = "neutral", children }: { tone?: BadgeTone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium capitalize ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  );
}
