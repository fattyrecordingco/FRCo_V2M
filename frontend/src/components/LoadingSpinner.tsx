export default function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="loading-spinner">
      <div className="loading-spinner-glyph" />
      <span>{label}</span>
    </div>
  );
}
