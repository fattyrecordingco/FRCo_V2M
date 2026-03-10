import { useEffect, useRef, useState } from "react";

interface Props {
  audioUrl: string | null;
}

export default function WaveformPreview({ audioUrl }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [canvasWidth, setCanvasWidth] = useState(680);
  const canvasHeight = 72;
  const [duration, setDuration] = useState(0);
  const [peaks, setPeaks] = useState<Float32Array | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const next = Math.max(120, Math.floor(entries[0].contentRect.width) - 2);
      setCanvasWidth(next);
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!audioUrl) {
      setPeaks(null);
      setDuration(0);
      return;
    }
    let disposed = false;
    const abortController = new AbortController();

    const loadPeaks = async () => {
      try {
        const res = await fetch(audioUrl, { signal: abortController.signal });
        const buf = await res.arrayBuffer();
        const ac = new AudioContext();
        try {
          const audioBuffer = await ac.decodeAudioData(buf);
          if (disposed) return;
          setDuration(audioBuffer.duration);
          const data = audioBuffer.getChannelData(0);
          const peakCount = 1024;
          const nextPeaks = new Float32Array(peakCount);
          const step = Math.max(1, Math.floor(data.length / peakCount));
          for (let i = 0; i < peakCount; i += 1) {
            let peak = 0;
            const start = i * step;
            const stop = Math.min(data.length, start + step);
            for (let j = start; j < stop; j += 1) {
              peak = Math.max(peak, Math.abs(data[j] ?? 0));
            }
            nextPeaks[i] = peak;
          }
          setPeaks(nextPeaks);
        } finally {
          await ac.close();
        }
      } catch {
        // Ignore transient decode/abort errors when source changes quickly.
      }
    };
    void loadPeaks();
    return () => {
      disposed = true;
      abortController.abort();
    };
  }, [audioUrl]);

  useEffect(() => {
    if (!canvasRef.current || !peaks) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const pixelRatio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(canvasWidth * pixelRatio);
    canvas.height = Math.floor(canvasHeight * pixelRatio);
    canvas.style.width = `${canvasWidth}px`;
    canvas.style.height = `${canvasHeight}px`;
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    const width = canvasWidth;
    const height = canvasHeight;
    const css = getComputedStyle(document.documentElement);
    const fill = css.getPropertyValue("--wave-bg").trim() || "#f3efe7";
    const stroke = css.getPropertyValue("--wave-line").trim() || "#58d872";

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = fill;
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = stroke;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i < width; i += 1) {
      const peakIdx = Math.min(peaks.length - 1, Math.floor((i / width) * peaks.length));
      const peak = peaks[peakIdx] ?? 0;
      ctx.moveTo(i, (1 - peak) * 0.5 * height);
      ctx.lineTo(i, (1 + peak) * 0.5 * height);
    }
    ctx.stroke();
  }, [canvasHeight, canvasWidth, peaks]);

  if (!audioUrl) {
    return (
      <div ref={containerRef} className="waveform-panel waveform-panel-empty">
        <div className="waveform-shell waveform-shell-empty">
          <div className="waveform-empty">No audio loaded yet. Record or upload to preview waveform.</div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="waveform-panel">
      <div className="waveform-shell">
        <canvas ref={canvasRef} width={canvasWidth} height={canvasHeight} className="waveform-canvas" />
      </div>
      <div className="waveform-meta">
        <span>Wave</span>
        <span>{duration.toFixed(2)}s</span>
      </div>
      <audio src={audioUrl} controls />
    </div>
  );
}
