export default function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-base-100 bg-white/10 px-3 py-2">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent-600 border-t-transparent" />
      <span className="text-xs font-semibold">{label}</span>
    </div>
  );
}
