export default function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-bpr-hairline/60 ${className}`} />;
}
