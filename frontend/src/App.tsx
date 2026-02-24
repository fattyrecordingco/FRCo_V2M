import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import * as Tone from "tone";

import FileTable from "./components/FileTable";
import LoadingSpinner from "./components/LoadingSpinner";
import MidiMiniView from "./components/MidiMiniView";
import PianoScalePicker from "./components/PianoScalePicker";
import WaveformPreview from "./components/WaveformPreview";
import {
  analyzeAudio,
  ensureBackendReady,
  fileUrl,
  getDemoFiles,
  getSessionFiles,
  getSessions,
  renameFile,
  zipUrl
} from "./lib/api";
import { AnalyzeResponse, FileEntry, Mode, MonoPolyOverride, SessionSummary } from "./lib/types";

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const SCALE_PRESETS: Record<string, string[]> = {
  major: ["C", "D", "E", "F", "G", "A", "B"],
  minor: ["C", "D", "D#", "F", "G", "G#", "A#"],
  dorian: ["C", "D", "D#", "F", "G", "A", "A#"],
  mixolydian: ["C", "D", "E", "F", "G", "A", "A#"],
  pentatonic_major: ["C", "D", "E", "G", "A"],
  pentatonic_minor: ["C", "D#", "F", "G", "A#"],
  blues: ["C", "D#", "F", "F#", "G", "A#"],
  chromatic: NOTE_NAMES
};

type InstrumentPreset = "piano" | "synth" | "acoustic_drums" | "electro_808";
type OutputTab = "midi" | "audio" | "sessions";
const AUDIO_EXT_PATTERN = /\.(wav|mp3|flac|ogg|m4a|aac|aiff|webm)$/i;
const RECORDER_MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

const initialTrackState = {
  notes: { mute: false, solo: false },
  chords: { mute: false, solo: false },
  drums: { mute: false, solo: false }
};

function pickRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return RECORDER_MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function extensionFromMimeType(mimeType: string): string {
  if (mimeType.includes("webm")) return "webm";
  if (mimeType.includes("mp4")) return "m4a";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

async function blobToWavFile(blob: Blob, filename: string): Promise<File> {
  const arrayBuffer = await blob.arrayBuffer();
  const audioCtx = new AudioContext();
  try {
    const decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
    const wavBlob = audioBufferToWavBlob(decoded);
    return new File([wavBlob], filename, { type: "audio/wav" });
  } finally {
    await audioCtx.close();
  }
}

function preprocessRecordedChannel(channel: Float32Array): Float32Array {
  const out = new Float32Array(channel.length);
  let mean = 0;
  let peak = 0;
  let avgAbs = 0;
  for (let i = 0; i < channel.length; i += 1) {
    const sample = channel[i] ?? 0;
    mean += sample;
    const abs = Math.abs(sample);
    avgAbs += abs;
    if (abs > peak) peak = abs;
  }
  mean /= Math.max(channel.length, 1);
  avgAbs /= Math.max(channel.length, 1);
  const gate = Math.max(avgAbs * 0.4, 0.0008);
  const gain = peak > 1e-6 ? Math.min(5.0, 0.9 / peak) : 1.0;

  for (let i = 0; i < channel.length; i += 1) {
    const centered = (channel[i] ?? 0) - mean;
    const abs = Math.abs(centered);
    let denoised = centered;
    if (abs < gate) denoised *= 0.18;
    else denoised = Math.sign(centered) * (abs - gate * 0.35);
    const amplified = denoised * gain;
    out[i] = Math.tanh(amplified * 1.04);
  }
  return out;
}

function audioBufferToWavBlob(buffer: AudioBuffer): Blob {
  const channels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const samples = buffer.length;
  const bytesPerSample = 2;
  const blockAlign = channels * bytesPerSample;
  const byteRate = sampleRate * blockAlign;
  const dataSize = samples * blockAlign;
  const wav = new ArrayBuffer(44 + dataSize);
  const view = new DataView(wav);

  let offset = 0;
  const writeString = (value: string) => {
    for (let i = 0; i < value.length; i += 1) {
      view.setUint8(offset + i, value.charCodeAt(i));
    }
    offset += value.length;
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + dataSize, true);
  offset += 4;
  writeString("WAVE");
  writeString("fmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint16(offset, channels, true);
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, byteRate, true);
  offset += 4;
  view.setUint16(offset, blockAlign, true);
  offset += 2;
  view.setUint16(offset, 16, true);
  offset += 2;
  writeString("data");
  view.setUint32(offset, dataSize, true);
  offset += 4;

  const channelData = Array.from({ length: channels }, (_, idx) =>
    preprocessRecordedChannel(buffer.getChannelData(idx))
  );
  for (let i = 0; i < samples; i += 1) {
    for (let ch = 0; ch < channels; ch += 1) {
      const sample = channelData[ch][i] ?? 0;
      const clamped = Math.max(-1, Math.min(1, sample));
      const pcm = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      view.setInt16(offset, pcm, true);
      offset += 2;
    }
  }
  return new Blob([wav], { type: "audio/wav" });
}

export default function App() {
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDevice, setSelectedDevice] = useState<string>("");
  const [isRecording, setIsRecording] = useState(false);
  const [recordLevel, setRecordLevel] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const meterCtxRef = useRef<AudioContext | null>(null);
  const meterSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const meterAnalyserRef = useRef<AnalyserNode | null>(null);
  const meterDataRef = useRef<Uint8Array | null>(null);
  const meterRafRef = useRef<number | null>(null);

  const [inputFile, setInputFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("auto");
  const [autoPitchTime, setAutoPitchTime] = useState(false);
  const [rootNote, setRootNote] = useState("C");
  const [scale, setScale] = useState("major");
  const [customScaleNotes, setCustomScaleNotes] = useState<string[]>(["C", "D", "E", "G", "A"]);
  const [bpm, setBpm] = useState(120);
  const [timeSignature, setTimeSignature] = useState("4/4");
  const [monoPolyOverride, setMonoPolyOverride] = useState<MonoPolyOverride>("auto");

  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [midiFiles, setMidiFiles] = useState<FileEntry[]>([]);
  const [audioFiles, setAudioFiles] = useState<FileEntry[]>([]);
  const [selectedPreview, setSelectedPreview] = useState<FileEntry | null>(null);
  const [outputTab, setOutputTab] = useState<OutputTab>("midi");

  const [instrument, setInstrument] = useState<InstrumentPreset>("piano");
  const [volume, setVolume] = useState(0.8);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loopEnabled, setLoopEnabled] = useState(false);
  const [trackState, setTrackState] = useState(initialTrackState);

  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSession, setActiveSession] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        await ensureBackendReady(30, 300);
        await loadSessions();
      } catch (error) {
        const message = error instanceof Error ? error.message : "Backend is not available.";
        setErrorMessage(message);
      }
    })();
    void refreshAudioDevices();
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      stopMeter();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const db = volume <= 0 ? -60 : 20 * Math.log10(volume);
    Tone.Destination.volume.value = db;
  }, [volume]);

  useEffect(() => {
    if (!result) return;
    if (autoPitchTime) {
      setBpm(Math.round(result.metadata.analysis.tempo_bpm));
      setTimeSignature(result.metadata.analysis.time_signature);
      setRootNote(result.metadata.analysis.root_note);
      if (scale !== "custom") setScale(result.metadata.analysis.scale);
    }
  }, [result, autoPitchTime, scale]);

  const noteEvents = useMemo(() => {
    if (!result) return [];
    if (selectedPreview?.name.includes("chords")) {
      return result.metadata.chord_events.flatMap((chord) =>
        chord.pitches.map((pitch) => ({
          pitch,
          start: chord.start,
          end: chord.end,
          velocity: 85
        }))
      );
    }
    if (selectedPreview?.name.includes("drums")) {
      return result.metadata.drum_events.map((hit) => ({
        pitch: hit.pitch,
        start: hit.start,
        end: hit.end,
        velocity: hit.velocity
      }));
    }
    return result.metadata.note_events;
  }, [result, selectedPreview]);

  function stopMeter() {
    if (meterRafRef.current !== null) {
      cancelAnimationFrame(meterRafRef.current);
      meterRafRef.current = null;
    }
    meterSourceRef.current?.disconnect();
    meterAnalyserRef.current?.disconnect();
    meterSourceRef.current = null;
    meterAnalyserRef.current = null;
    meterDataRef.current = null;
    if (meterCtxRef.current) {
      void meterCtxRef.current.close();
      meterCtxRef.current = null;
    }
    setRecordLevel(0);
  }

  function startMeter(stream: MediaStream) {
    stopMeter();
    const ctx = new AudioContext();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.82;
    source.connect(analyser);
    const data = new Uint8Array(analyser.fftSize);

    meterCtxRef.current = ctx;
    meterSourceRef.current = source;
    meterAnalyserRef.current = analyser;
    meterDataRef.current = data;

    const tick = () => {
      const currentAnalyser = meterAnalyserRef.current;
      const currentData = meterDataRef.current;
      if (!currentAnalyser || !currentData) return;
      currentAnalyser.getByteTimeDomainData(currentData);
      let peak = 0;
      for (let i = 0; i < currentData.length; i += 1) {
        const centered = Math.abs((currentData[i] - 128) / 128);
        if (centered > peak) peak = centered;
      }
      const normalized = Math.min(1, peak * 1.65);
      setRecordLevel((prev) => prev * 0.45 + normalized * 0.55);
      meterRafRef.current = requestAnimationFrame(tick);
    };

    meterRafRef.current = requestAnimationFrame(tick);
  }

  async function loadSessions() {
    try {
      const sessionRows = await getSessions();
      setSessions(sessionRows);
    } catch {
      setSessions([]);
    }
  }

  async function refreshAudioDevices() {
    try {
      const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      permissionStream.getTracks().forEach((track) => track.stop());
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs = devices.filter((device) => device.kind === "audioinput");
      setAudioDevices(inputs);
      if (inputs.length > 0 && !selectedDevice) {
        setSelectedDevice(inputs[0].deviceId);
      }
    } catch {
      setErrorMessage("Microphone permissions were denied or unavailable.");
    }
  }

  function onFilePicked(file: File) {
    const hasAudioMime = file.type.startsWith("audio/");
    const hasAudioExtension = AUDIO_EXT_PATTERN.test(file.name);
    if (!hasAudioMime && !hasAudioExtension) {
      setErrorMessage("Unsupported file type. Please upload an audio file.");
      return;
    }
    setErrorMessage(null);
    setInputFile(file);
    setSelectedPreview(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    const nextUrl = URL.createObjectURL(file);
    setAudioUrl(nextUrl);
  }

  function onUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onFilePicked(file);
  }

  function onDropAudio(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (file) onFilePicked(file);
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
  }

  async function startRecording() {
    setErrorMessage(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: selectedDevice ? { deviceId: { exact: selectedDevice } } : true
      });
      streamRef.current = stream;
      startMeter(stream);
      const mimeType = pickRecorderMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (evt) => {
        if (evt.data.size > 0) chunksRef.current.push(evt.data);
      };
      recorder.onstop = async () => {
        const actualType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type: actualType });
        try {
          const wavFile = await blobToWavFile(blob, `recording_${Date.now()}.wav`);
          onFilePicked(wavFile);
        } catch {
          const extension = extensionFromMimeType(actualType);
          const fallback = new File([blob], `recording_${Date.now()}.${extension}`, { type: actualType });
          onFilePicked(fallback);
          setErrorMessage(
            "Recording was captured in a compressed format. If generation fails, upload as WAV/MP3."
          );
        }
        stopMeter();
        stream.getTracks().forEach((track) => track.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      setIsRecording(true);
    } catch {
      stopMeter();
      setErrorMessage("Could not start recording from selected device.");
    }
  }

  function stopRecording() {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
    stopMeter();
    setIsRecording(false);
  }

  async function handleTryDemo() {
    try {
      await ensureBackendReady(20, 250);
      const demo = await getDemoFiles();
      if (!demo.length) {
        setErrorMessage("No demo audio found in /examples.");
        return;
      }
      const first = demo[0];
      const response = await fetch(fileUrl(first.url));
      const blob = await response.blob();
      const file = new File([blob], first.name, { type: "audio/wav" });
      onFilePicked(file);
    } catch {
      setErrorMessage("Unable to load demo file.");
    }
  }

  async function handleGenerate() {
    if (!inputFile) {
      setErrorMessage("Please record or upload audio before generating.");
      return;
    }
    setProcessing(true);
    setErrorMessage(null);
    setIsPlaying(false);
    Tone.Transport.stop();
    Tone.Transport.cancel();
    try {
      await ensureBackendReady(25, 250);
      const response = await analyzeAudio({
        file: inputFile,
        mode,
        autoPitchTime,
        rootNote,
        scale,
        customScaleNotes,
        bpm,
        timeSignature,
        monoPolyOverride,
        sessionId: sessionId ?? undefined
      });
      setResult(response);
      setSessionId(response.session_id);
      setActiveSession(response.session_id);
      await loadSessionFiles(response.session_id, response);
      await loadSessions();
      const defaultPreview = response.midi_files[0] ?? response.audio_files[0] ?? null;
      setSelectedPreview(defaultPreview);
      setOutputTab("midi");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Processing failed.";
      setErrorMessage(message);
    } finally {
      setProcessing(false);
    }
  }

  async function loadSessionFiles(targetSession: string, latestResult?: AnalyzeResponse) {
    const files = await getSessionFiles(targetSession);
    setMidiFiles(files.midi);
    setAudioFiles(files.audio);
    if (!latestResult) {
      setResult((prev) => prev);
      setSelectedPreview((files.midi[0] ?? files.audio[0] ?? null) as FileEntry | null);
    }
  }

  async function handleSelectSession(session: string) {
    setActiveSession(session);
    setSessionId(session);
    try {
      await loadSessionFiles(session);
    } catch {
      setErrorMessage("Unable to load files for this session.");
    }
  }

  async function onRename(file: FileEntry) {
    if (!sessionId) return;
    const newName = window.prompt("Rename file", file.name);
    if (!newName || newName === file.name) return;
    try {
      await renameFile(sessionId, file.relative_path, newName);
      await loadSessionFiles(sessionId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Rename failed.";
      setErrorMessage(message);
    }
  }

  function onSelectPreview(file: FileEntry) {
    setSelectedPreview(file);
    if (file.kind === "audio") {
      const host = (import.meta.env.VITE_API_URL as string | undefined)?.replace("/api/v1", "") ?? "http://127.0.0.1:8000";
      setAudioUrl(`${host}${file.url}`);
    }
  }

  async function playPreview() {
    if (!result) return;
    await Tone.start();
    Tone.Transport.stop();
    Tone.Transport.cancel();

    const hasSolo = Object.values(trackState).some((track) => track.solo);
    const canPlayTrack = (track: "notes" | "chords" | "drums") => {
      if (hasSolo) return trackState[track].solo;
      return !trackState[track].mute;
    };

    const notesSynth =
      instrument === "piano"
        ? new Tone.PolySynth(Tone.Synth, { oscillator: { type: "triangle" } }).toDestination()
        : new Tone.PolySynth(Tone.Synth, { oscillator: { type: "sawtooth" } }).toDestination();
    const chordSynth = new Tone.PolySynth(Tone.Synth, { oscillator: { type: "sine" } }).toDestination();
    const kick = new Tone.MembraneSynth().toDestination();
    const snare = new Tone.NoiseSynth({ envelope: { attack: 0.001, decay: 0.1, sustain: 0 } }).toDestination();
    const hat = new Tone.MetalSynth().toDestination();

    if (canPlayTrack("notes")) {
      result.metadata.note_events.forEach((note) => {
        Tone.Transport.schedule((time) => {
          notesSynth.triggerAttackRelease(
            Tone.Frequency(note.pitch, "midi").toFrequency(),
            Math.max(note.end - note.start, 0.05),
            time,
            note.velocity / 127
          );
        }, note.start);
      });
    }

    if (canPlayTrack("chords")) {
      result.metadata.chord_events.forEach((chord) => {
        Tone.Transport.schedule((time) => {
          const freqs = chord.pitches.map((pitch) => Tone.Frequency(pitch, "midi"));
          chordSynth.triggerAttackRelease(
            freqs.map((frequency) => frequency.toFrequency()),
            Math.max(chord.end - chord.start, 0.1),
            time,
            0.6
          );
        }, chord.start);
      });
    }

    if (canPlayTrack("drums")) {
      result.metadata.drum_events.forEach((hit) => {
        Tone.Transport.schedule((time) => {
          if (hit.class.includes("kick")) {
            kick.triggerAttackRelease("C1", "16n", time, 0.85);
          } else if (hit.class.includes("hihat")) {
            hat.triggerAttackRelease("16n", time, 0.35);
          } else {
            snare.triggerAttackRelease("16n", time, 0.55);
          }
        }, hit.start);
      });
    }

    const totalLength = Math.max(
      ...result.metadata.note_events.map((event) => event.end),
      ...result.metadata.chord_events.map((event) => event.end),
      ...result.metadata.drum_events.map((event) => event.end),
      2
    );
    Tone.Transport.loop = loopEnabled;
    Tone.Transport.loopStart = 0;
    Tone.Transport.loopEnd = totalLength;
    Tone.Transport.start("+0.05");
    setIsPlaying(true);

    Tone.Transport.scheduleOnce(() => {
      if (!loopEnabled) setIsPlaying(false);
      notesSynth.dispose();
      chordSynth.dispose();
      kick.dispose();
      snare.dispose();
      hat.dispose();
    }, totalLength + 0.1);
  }

  function pausePreview() {
    Tone.Transport.pause();
    setIsPlaying(false);
  }

  const suggestedScaleNotes = SCALE_PRESETS[scale] ?? NOTE_NAMES;
  const previewName = selectedPreview?.name ?? "No preview file selected";
  const folderFiles = [...midiFiles, ...audioFiles];
  const activeSessionId = activeSession ?? sessionId ?? "";

  return (
    <main className="app-shell">
      <div className="app-frame">
        <header className="panel app-header">
          <div>
            <h1 className="font-display text-2xl font-bold">VINS</h1>
            <p className="text-xs text-slate-600">Voice Input Notation System</p>
          </div>
          <div className="header-actions">
            <button type="button" className="btn btn-secondary" onClick={handleTryDemo}>
              Try Demo
            </button>
            <span className="step-pill">1 Input</span>
            <span className="step-pill">2 Prep</span>
            <span className="step-pill">3 Preview</span>
            <span className="step-pill">4 Export</span>
          </div>
        </header>

        {errorMessage && <div className="panel app-error">{errorMessage}</div>}

        <div className="app-grid">
          <section className="panel step-panel step-input">
            <div className="step-title-row">
              <h2 className="font-display text-lg font-semibold">Step 1: Input</h2>
            </div>
            <div className="field-grid">
              <label className="field-label" htmlFor="device-select">
                Input Device
              </label>
              <select
                id="device-select"
                className="input"
                value={selectedDevice}
                onChange={(event) => setSelectedDevice(event.target.value)}
              >
                {audioDevices.map((device) => (
                  <option key={device.deviceId} value={device.deviceId}>
                    {device.label || `Input ${device.deviceId.slice(0, 6)}`}
                  </option>
                ))}
              </select>
            </div>

            <div className="compact-row">
              {!isRecording ? (
                <button type="button" className="btn btn-primary" onClick={startRecording}>
                  Record Mic Input
                </button>
              ) : (
                <button type="button" className="btn btn-primary btn-danger" onClick={stopRecording}>
                  Stop Recording
                </button>
              )}
              <label className="btn btn-secondary cursor-pointer">
                or Upload
                <input type="file" accept="audio/*" className="hidden" onChange={onUploadChange} />
              </label>
            </div>

            <div className={`recording-meter ${isRecording ? "is-live" : ""}`}>
              <div className="recording-meter-bar">
                <span style={{ width: `${Math.max(4, Math.round(recordLevel * 100))}%` }} />
              </div>
              <span className="recording-meter-label">{isRecording ? "Recording" : "Idle"}</span>
            </div>

            <div
              className="rounded-2xl border border-dashed border-base-100 p-4 text-center text-sm"
              onDrop={onDropAudio}
              onDragOver={onDragOver}
            >
              Drag and drop audio files here
            </div>

            <WaveformPreview audioUrl={audioUrl} />
          </section>

          <div className="middle-stack">
            <section className="panel step-panel step-prep">
              <div className="step-title-row">
                <h2 className="font-display text-lg font-semibold">Step 2: Pre-Processing</h2>
              </div>

              <div className="mode-grid">
                <button
                  type="button"
                  className={`btn ${mode === "notes" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setMode("notes")}
                >
                  Notes (Mono)
                </button>
                <button
                  type="button"
                  className={`btn ${mode === "chords" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setMode("chords")}
                >
                  Chords (Poly)
                </button>
                <button
                  type="button"
                  className={`btn ${mode === "drums" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setMode("drums")}
                >
                  Drums
                </button>
                <button
                  type="button"
                  className={`btn ${mode === "auto" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setMode("auto")}
                >
                  Auto
                </button>
              </div>

              <label className="toggle-row">
                <span>Auto Pitch &amp; Time</span>
                <input
                  type="checkbox"
                  checked={autoPitchTime}
                  onChange={(event) => setAutoPitchTime(event.target.checked)}
                  className="h-4 w-4"
                />
              </label>

              <div className="prep-grid">
                <div>
                  <label className="field-label">Root</label>
                  <select className="input" value={rootNote} onChange={(event) => setRootNote(event.target.value)}>
                    {NOTE_NAMES.map((note) => (
                      <option key={note} value={note}>
                        {note}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label">Scale</label>
                  <select className="input" value={scale} onChange={(event) => setScale(event.target.value)}>
                    {Object.keys(SCALE_PRESETS).map((label) => (
                      <option key={label} value={label}>
                        {label}
                      </option>
                    ))}
                    <option value="custom">custom</option>
                  </select>
                </div>
                <div>
                  <label className="field-label">BPM</label>
                  <input
                    type="number"
                    className="input"
                    value={bpm}
                    min={20}
                    max={320}
                    onChange={(event) => setBpm(Number(event.target.value))}
                  />
                </div>
                <div>
                  <label className="field-label">Time Sig</label>
                  <input
                    type="text"
                    className="input"
                    value={timeSignature}
                    onChange={(event) => setTimeSignature(event.target.value)}
                  />
                </div>
              </div>

              <div className="field-grid">
                <label className="field-label">Mono/Poly</label>
                <select
                  className="input"
                  value={monoPolyOverride}
                  onChange={(event) => setMonoPolyOverride(event.target.value as MonoPolyOverride)}
                >
                  <option value="auto">Auto Detect</option>
                  <option value="mono">Monophonic</option>
                  <option value="poly">Polyphonic</option>
                </select>
              </div>

              {scale === "custom" ? (
                <PianoScalePicker selected={customScaleNotes} onChange={setCustomScaleNotes} />
              ) : (
                <div className="scale-note-summary">Scale notes: {suggestedScaleNotes.join(" - ")}</div>
              )}

              <button type="button" className="btn btn-primary generate-btn" onClick={handleGenerate} disabled={processing}>
                Generate
              </button>
            </section>

            <section className="panel step-panel step-preview">
              <div className="step-title-row">
                <h2 className="font-display text-lg font-semibold">Step 3: Processing &amp; Preview</h2>
              </div>
              {processing && <LoadingSpinner label="Analyzing and generating MIDI/audio..." />}
              {!processing && (
                <>
                  <div className="preview-current">
                    <span className="font-semibold">Current preview:</span>
                    <span className="truncate">{previewName}</span>
                  </div>

                  <MidiMiniView notes={noteEvents} />

                  <div className="instrument-grid">
                    <button
                      type="button"
                      className={`btn ${instrument === "piano" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setInstrument("piano")}
                    >
                      Basic Piano
                    </button>
                    <button
                      type="button"
                      className={`btn ${instrument === "synth" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setInstrument("synth")}
                    >
                      Synth Pad
                    </button>
                    <button
                      type="button"
                      className={`btn ${instrument === "acoustic_drums" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setInstrument("acoustic_drums")}
                    >
                      Acoustic Drum Kit
                    </button>
                    <button
                      type="button"
                      className={`btn ${instrument === "electro_808" ? "btn-primary" : "btn-secondary"}`}
                      onClick={() => setInstrument("electro_808")}
                    >
                      808 Electronic Drum Kit
                    </button>
                  </div>

                  <div className="compact-row">
                    {!isPlaying ? (
                      <button type="button" className="btn btn-primary" onClick={playPreview}>
                        Play
                      </button>
                    ) : (
                      <button type="button" className="btn btn-secondary" onClick={pausePreview}>
                        Pause
                      </button>
                    )}
                    <label className="slider-row">
                      Volume
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={volume}
                        onChange={(event) => setVolume(Number(event.target.value))}
                      />
                    </label>
                    <label className="toggle-inline">
                      Loop
                      <input
                        type="checkbox"
                        checked={loopEnabled}
                        onChange={(event) => setLoopEnabled(event.target.checked)}
                      />
                    </label>
                  </div>

                  <div className="track-grid">
                    {(["notes", "chords", "drums"] as const).map((track) => (
                      <div key={track} className="track-card">
                        <div className="font-semibold uppercase">{track}</div>
                        <label className="toggle-inline">
                          <input
                            type="checkbox"
                            checked={trackState[track].mute}
                            onChange={(event) =>
                              setTrackState((prev) => ({
                                ...prev,
                                [track]: { ...prev[track], mute: event.target.checked }
                              }))
                            }
                          />
                          Mute
                        </label>
                        <label className="toggle-inline">
                          <input
                            type="checkbox"
                            checked={trackState[track].solo}
                            onChange={(event) =>
                              setTrackState((prev) => ({
                                ...prev,
                                [track]: { ...prev[track], solo: event.target.checked }
                              }))
                            }
                          />
                          Solo
                        </label>
                      </div>
                    ))}
                  </div>

                  <div className="folder-strip">
                    {folderFiles.length === 0 && <span className="muted-text">No generated files yet.</span>}
                    {folderFiles.slice(0, 6).map((file) => (
                      <div
                        key={`folder-${file.relative_path}`}
                        className={`folder-chip ${selectedPreview?.relative_path === file.relative_path ? "is-active" : ""}`}
                        onDoubleClick={() => onSelectPreview(file)}
                      >
                        <button type="button" className="chip-button" onClick={() => onSelectPreview(file)}>
                          {file.name}
                        </button>
                        <span className="chip-tag">{file.kind}</span>
                      </div>
                    ))}
                    {folderFiles.length > 6 && <span className="muted-text">+{folderFiles.length - 6} more files in archive</span>}
                  </div>
                </>
              )}
            </section>
          </div>

          <section className="panel step-panel step-output">
            <div className="step-title-row">
              <h2 className="font-display text-lg font-semibold">Step 4: Output &amp; File Management</h2>
            </div>

            <div className="field-grid">
              <label className="field-label" htmlFor="session-select">
                Session
              </label>
              <select
                id="session-select"
                className="input"
                value={activeSessionId}
                onChange={(event) => {
                  const nextSession = event.target.value;
                  if (nextSession) void handleSelectSession(nextSession);
                }}
              >
                {!activeSessionId && <option value="">No active session</option>}
                {sessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.session_id} ({session.run_count} runs)
                  </option>
                ))}
              </select>
            </div>

            <div className="output-tab-row">
              <button
                type="button"
                className={`btn ${outputTab === "midi" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setOutputTab("midi")}
              >
                MIDI
              </button>
              <button
                type="button"
                className={`btn ${outputTab === "audio" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setOutputTab("audio")}
              >
                Audio
              </button>
              <button
                type="button"
                className={`btn ${outputTab === "sessions" ? "btn-primary" : "btn-secondary"}`}
                onClick={() => setOutputTab("sessions")}
              >
                Sessions
              </button>
            </div>

            {outputTab !== "sessions" && (
              <FileTable
                title={outputTab === "midi" ? "MIDI Files" : "Audio Files"}
                files={outputTab === "midi" ? midiFiles : audioFiles}
                selectedPath={selectedPreview?.relative_path ?? null}
                onSelect={onSelectPreview}
                onRename={onRename}
              />
            )}

            {outputTab === "sessions" && (
              <div className="session-list">
                {sessions.length === 0 && <div className="muted-text">No sessions saved yet.</div>}
                {sessions.slice(0, 7).map((session) => (
                  <button
                    key={session.session_id}
                    type="button"
                    className={`session-item ${activeSession === session.session_id ? "is-active" : ""}`}
                    onClick={() => handleSelectSession(session.session_id)}
                  >
                    <span className="session-id">{session.session_id}</span>
                    <span className="session-meta">
                      {session.run_count} runs - {session.source_file}
                    </span>
                  </button>
                ))}
                {sessions.length > 7 && <div className="muted-text">+{sessions.length - 7} more sessions</div>}
              </div>
            )}

            <div className="zip-row">
              {sessionId ? (
                <a className="btn btn-primary" href={zipUrl(sessionId)} download>
                  Download ZIP
                </a>
              ) : (
                <span className="muted-text">Generate once to enable ZIP export.</span>
              )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
