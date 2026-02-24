import { useEffect, useRef, useState } from "react";

interface Props {
  audioUrl: string | null;
}

export default function WaveformPreview({ audioUrl }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    if (!audioUrl || !canvasRef.current) return;
    let disposed = false;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const draw = async () => {
      const res = await fetch(audioUrl);
      const buf = await res.arrayBuffer();
      const ac = new AudioContext();
      const audioBuffer = await ac.decodeAudioData(buf);
      if (disposed) return;
      setDuration(audioBuffer.duration);
      const data = audioBuffer.getChannelData(0);
      const width = canvas.width;
      const height = canvas.height;
      const step = Math.max(1, Math.floor(data.length / width));

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "#29783B";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let i = 0; i < width; i += 1) {
        let min = 1;
        let max = -1;
        for (let j = 0; j < step; j += 1) {
          const datum = data[i * step + j] ?? 0;
          if (datum < min) min = datum;
          if (datum > max) max = datum;
        }
        ctx.moveTo(i, (1 + min) * 0.5 * height);
        ctx.lineTo(i, (1 + max) * 0.5 * height);
      }
      ctx.stroke();
      ac.close();
    };
    void draw();
    return () => {
      disposed = true;
    };
  }, [audioUrl]);

  if (!audioUrl) {
    return <div className="text-xs text-slate-500">No audio loaded.</div>;
  }

  return (
    <div className="space-y-1">
      <canvas ref={canvasRef} width={720} height={86} className="w-full rounded-xl" />
      <div className="flex items-center justify-between text-[11px] text-slate-600">
        <span>Waveform Preview</span>
        <span>{duration.toFixed(2)}s</span>
      </div>
      <audio src={audioUrl} controls className="w-full" />
    </div>
  );
}
