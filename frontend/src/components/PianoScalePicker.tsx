const NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const WHITE_KEYS = ["C", "D", "E", "F", "G", "A", "B"];
const BLACK_KEYS: Array<{ note: string; leftPercent: number }> = [
  { note: "C#", leftPercent: 10.6 },
  { note: "D#", leftPercent: 24.8 },
  { note: "F#", leftPercent: 53.3 },
  { note: "G#", leftPercent: 67.6 },
  { note: "A#", leftPercent: 81.9 }
];

interface Props {
  selected: string[];
  onChange: (next: string[]) => void;
  lockedNotes?: string[];
}

export default function PianoScalePicker({ selected, onChange, lockedNotes = [] }: Props) {
  const activeSet = new Set(selected);
  const lockedSet = new Set(lockedNotes);

  const toggle = (note: string) => {
    if (lockedSet.has(note)) return;
    const next = new Set(activeSet);
    if (next.has(note)) next.delete(note);
    else next.add(note);
    onChange(NOTES.filter((n) => next.has(n)));
  };

  const isActive = (note: string) => activeSet.has(note) || lockedSet.has(note);

  return (
    <div className="space-y-2">
      <div className="text-xs font-semibold">Scale Keys</div>
      <div className="relative select-none rounded-xl border border-base-100 bg-slate-100 p-2">
        <div className="relative h-24">
          <div className="absolute inset-0 grid grid-cols-7 gap-1">
            {WHITE_KEYS.map((note) => (
              <button
                key={note}
                type="button"
                onClick={() => toggle(note)}
                className={`relative rounded-b-lg border pb-1 pt-12 text-center text-[11px] font-semibold transition ${
                  isActive(note)
                    ? "border-accent-500 bg-accent-500/90 text-white"
                    : "border-base-200 bg-white text-slate-800"
                }`}
              >
                {note}
              </button>
            ))}
          </div>
          {BLACK_KEYS.map((key) => (
            <button
              key={key.note}
              type="button"
              onClick={() => toggle(key.note)}
              style={{ left: `${key.leftPercent}%` }}
              className={`absolute top-0 z-10 h-14 w-[8.6%] -translate-x-1/2 rounded-b-md border border-slate-900 text-center text-[10px] font-semibold transition ${
                isActive(key.note)
                  ? "bg-accent-500 text-white"
                  : "bg-slate-900 text-slate-100 hover:bg-slate-800"
              }`}
            >
              {key.note}
            </button>
          ))}
        </div>
      </div>
      <div className="text-[11px] text-slate-500">
        One octave (C-B). Click keys to set scale.
      </div>
    </div>
  );
}
