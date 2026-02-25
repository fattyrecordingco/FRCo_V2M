interface NoteEvent {
  pitch: number;
  start: number;
  end: number;
  velocity: number;
}

export default function MidiMiniView({ notes }: { notes: NoteEvent[] }) {
  if (notes.length === 0) {
    return <div className="muted-text">No MIDI notes yet.</div>;
  }

  const total = Math.max(...notes.map((note) => note.end), 1);
  return (
    <div className="midi-mini">
      <div className="midi-mini-head">
        <span>MIDI View</span>
        <span>{notes.length} notes</span>
      </div>
      <div className="midi-mini-chart">
        {notes.slice(0, 64).map((note, idx) => {
          const left = (note.start / total) * 100;
          const width = ((note.end - note.start) / total) * 100;
          const top = 100 - ((note.pitch - 24) / 84) * 100;
          return (
            <div
              key={`${note.pitch}-${idx}-${note.start}`}
              className="midi-mini-note"
              style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%`, top: `${top}%` }}
            />
          );
        })}
      </div>
    </div>
  );
}
