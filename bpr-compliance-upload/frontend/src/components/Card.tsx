export default function Card({
  children,
  className = "",
  padded = true,
}: {
  children: React.ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-bpr-hairline bg-bpr-card shadow-ledger ${padded ? "p-5" : ""} ${className}`}
    >
      {children}
    </div>
  );
}
