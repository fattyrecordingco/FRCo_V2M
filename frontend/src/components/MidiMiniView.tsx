interface NoteEvent {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
}

export default function MidiMiniView({ notes }: { notes: NoteEvent[] }) {
  if (notes.length === 0) {
    return <div className="text-xs text-slate-500">No MIDI notes yet.</div>;
  }

  const total = Math.max(...notes.map((note) => note.end), 1);
  return (
    <div className="space-y-1">
      <div className="text-xs font-semibold">MIDI View</div>
      <div className="relative h-16 rounded-lg border border-base-100 bg-base-50">
        {notes.slice(0, 64).map((note, idx) => {
          const left = (note.start / total) * 100;
          const width = ((note.end - note.start) / total) * 100;
          const top = 100 - ((note.pitch - 24) / 84) * 100;
          return (
            <div
              key={`${note.pitch}-${idx}-${note.start}`}
              className="absolute h-1.5 rounded bg-accent-500"
              style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%`, top: `${top}%` }}
            />
          );
        })}
      </div>
      <div className="grid gap-0.5 text-[11px] text-slate-600">
        {notes.slice(0, 4).map((note, idx) => (
          <div key={`list-${idx}-${note.start}`} className="flex justify-between py-0.5">
            <span>Pitch {note.pitch}</span>
            <span>
              {note.start.toFixed(2)}s - {note.end.toFixed(2)}s
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
