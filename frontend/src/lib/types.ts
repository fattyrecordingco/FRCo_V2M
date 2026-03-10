export type Mode = "notes" | "chords" | "drums" | "auto" | "control";
export type MonoPolyOverride = "auto" | "mono" | "poly";
export type WorkflowMode = "live" | "studio" | "hybrid";
export type FeelMode = "preserve" | "balanced" | "tight";

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
      percussive_ratio?: number;
      processing_latency_ms?: number;
      input_enhancement?: Record<string, number>;
    };
    note_events: Array<{
      pitch: number;
      start: number;
      end: number;
      velocity: number;
      confidence?: number;
      articulation?: string;
      vibrato_cents?: number;
      drift_cents?: number;
      pitch_curve?: Array<{ time: number; midi: number }>;
      expression_curve?: Array<{ time: number; value: number }>;
    }>;
    chord_events: Array<{ label: string; pitches: number[]; start: number; end: number; confidence: number }>;
    drum_events: Array<{
      pitch: number;
      class: string;
      start: number;
      end: number;
      velocity: number;
      confidence: number;
    }>;
    controller?: {
      frames?: Array<{
        time: number;
        voiced: boolean;
        voiced_score: number;
        pitch_hz?: number | null;
        pitch_midi?: number | null;
        loudness: number;
        brightness: number;
        vibrato: number;
        onset: number;
      }>;
      events?: {
        notes?: Array<{ pitch: number; start: number; end: number; velocity: number }>;
        cc?: Array<{ time: number; number: number; value: number }>;
        pitch_bends?: Array<{ time: number; value: number }>;
      };
      summary?: Record<string, unknown>;
    } | null;
    profile?: Record<string, unknown> | null;
    suggestions?: {
      role?: string;
      harmonic_role?: string;
      production?: Array<{ title: string; reason: string }>;
      sound_design?: Array<{ title: string; reason: string }>;
      arrangement?: Array<{ title: string; reason: string }>;
      explanation?: Record<string, unknown>;
    } | null;
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
