export default function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-bpr-hairline py-14 text-center">
      <p className="text-[13.5px] font-medium text-bpr-ink2/70">{title}</p>
      {hint && <p className="mt-1 max-w-xs text-[12.5px] text-bpr-ink2/45">{hint}</p>}
    </div>
  );
}
