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
    <div className="piano-root">
      <div className="piano-label-row">
        <span className="field-label">Scale Keys</span>
      </div>
      <div className="piano-wrap">
        <div className="piano-scroll">
          <div className="piano-frame" data-testid="piano-picker">
            <div className="piano-white-row">
              {WHITE_KEYS.map((note) => (
                <button
                  key={note}
                  type="button"
                  onClick={() => toggle(note)}
                  title={`Toggle ${note}`}
                  aria-pressed={isActive(note)}
                  className={`piano-key piano-key-white ${
                    isActive(note)
                      ? "piano-key-active"
                      : "piano-key-inactive"
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
                title={`Toggle ${key.note}`}
                aria-pressed={isActive(key.note)}
                className={`piano-key piano-key-black ${
                  isActive(key.note)
                    ? "piano-key-active"
                    : "piano-key-inactive"
                }`}
              >
                {key.note}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
