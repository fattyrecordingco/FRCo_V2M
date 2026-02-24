export type Mode = "notes" | "chords" | "drums" | "auto";
export type MonoPolyOverride = "auto" | "mono" | "poly";

export interface FileEntry {
  name: string;
  relative_path: string;
  kind: "midi" | "audio";
  mime_type: string;
  run_id: string;
  selected: boolean;
  url: string;
  base64?: string | null;
}

export interface AnalyzeResponse {
  session_id: string;
  run_id: string;
  mode_used: Mode;
  metadata: {
    analysis: {
      tempo_bpm: number;
      time_signature: string;
      root_note: string;
      scale: string;
      key_confidence: number;
      mono_poly_label: string;
      mono_poly_confidence: number;
      selected_bpm: number;
      selected_time_signature: string;
      selected_root_note: string;
      selected_scale: string;
    };
    note_events: Array<{ pitch: number; start: number; end: number; velocity: number }>;
    chord_events: Array<{ label: string; pitches: number[]; start: number; end: number; confidence: number }>;
    drum_events: Array<{
      pitch: number;
      class: string;
      start: number;
      end: number;
      velocity: number;
      confidence: number;
    }>;
    user_selections: Record<string, unknown>;
    detection_confidence: Record<string, number>;
  };
  midi_files: FileEntry[];
  audio_files: FileEntry[];
}

export interface SessionSummary {
  session_id: string;
  created_at: string;
  updated_at: string;
  latest_mode: string;
  run_count: number;
  source_file: string;
}

