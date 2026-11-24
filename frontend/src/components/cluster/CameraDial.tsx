import { useEffect, useRef, useState } from "react";
import { Camera, CameraOff } from "lucide-react";
import { useCameraDetection } from "@/hooks/use-camera-detection";
import { arcPath, polar } from "./dial-math";

const START = 0;
const END = 180;
const MAX = 8;

type CamState = "off" | "starting" | "on" | "error";

export function CameraDial() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [state, setState] = useState<CamState>("off");
  const [error, setError] = useState("");
  const detectorOffline = useCameraDetection(videoRef, state === "on");

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), []);

  async function start() {
    setState("starting");
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      video.srcObject = stream;
      await video.play();
      setState("on");
    } catch (e) {
      stop();
      setError(
        e instanceof DOMException && e.name === "NotAllowedError"
          ? "Permite accesul la cameră din browser."
          : "Camera nu a putut porni.",
      );
      setState("error");
    }
  }

  function stop() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setState("off");
  }

  const ticks: number[] = [];
  for (let i = 0; i <= MAX * 2; i++) ticks.push(START + ((END - START) / (MAX * 2)) * i);

  return (
    <div className="dial-ring relative aspect-square w-full rounded-full">
      {/* Camera feed fills the dial face — this replaces the gear selector */}
      <div className="absolute inset-[21%] overflow-hidden rounded-full bg-cluster">
        <video
          ref={videoRef}
          playsInline
          muted
          className={`h-full w-full object-cover transition-opacity duration-500 ${state === "on" ? "opacity-100" : "opacity-0"}`}
        />
        {state === "on" && (
          <div className="pointer-events-none absolute inset-0">
            <div className="scan-line h-1/3 w-full" />
          </div>
        )}
        {state !== "on" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center">
            <button
              onClick={start}
              disabled={state === "starting"}
              className="flex flex-col items-center gap-2 rounded-full p-4 text-foreground transition-colors hover:text-primary disabled:opacity-50"
            >
              <Camera className="h-[clamp(1.5rem,3.5cqw,3rem)] w-[clamp(1.5rem,3.5cqw,3rem)]" />
              <span className="text-[clamp(0.7rem,1.4cqw,1.1rem)] font-semibold uppercase tracking-widest">
                {state === "starting" ? "Se pornește…" : "Pornește camera"}
              </span>
            </button>
            {error && <p className="text-[clamp(0.6rem,1.1cqw,0.9rem)] text-signal">{error}</p>}
          </div>
        )}
      </div>

      <svg viewBox="0 0 200 200" className="pointer-events-none absolute inset-0 h-full w-full">
        {/* power / charge arcs on the left like the original cluster */}
        <path d={arcPath(97, 205, 268)} stroke="var(--glow)" strokeWidth="4" fill="none" />
        <path d={arcPath(97, 272, 330)} stroke="var(--eco)" strokeWidth="4" fill="none" />
        <path d={arcPath(97, START, END)} stroke="var(--glow)" strokeWidth="1.5" fill="none" opacity="0.7" />
        <path d={arcPath(91, 157.5, 180)} stroke="var(--signal)" strokeWidth="3" fill="none" />
        {ticks.map((a, i) => {
          const major = i % 2 === 0;
          const [x0, y0] = polar(major ? 84 : 88, a);
          const [x1, y1] = polar(93, a);
          return (
            <line key={i} x1={x0} y1={y0} x2={x1} y2={y1} stroke="var(--dial-tick)" strokeWidth={major ? 2 : 1} />
          );
        })}
        {Array.from({ length: MAX + 1 }, (_, n) => {
          const [x, y] = polar(73, START + ((END - START) / MAX) * n);
          return n === 0 ? null : (
            <text
              key={n}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fill="var(--foreground)"
              fontFamily="var(--font-display)"
              fontWeight="600"
              fontSize="11"
            >
              {n}
            </text>
          );
        })}
        <text x="12" y="72" fill="var(--glow)" fontSize="7" fontFamily="var(--font-display)">%Pwr</text>
        <text x="14" y="108" fill="var(--eco)" fontSize="7" fontFamily="var(--font-display)">%Ch</text>
      </svg>

      {state === "on" && (
        <button
          onClick={stop}
          aria-label="Oprește camera"
          className="absolute bottom-[23%] left-1/2 flex -translate-x-1/2 items-center gap-1 rounded-full bg-cluster/80 px-3 py-1 text-[clamp(0.6rem,1cqw,0.8rem)] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground"
        >
          <CameraOff className="h-3 w-3" /> Oprește
        </button>
      )}
      {state === "on" && (
        <span className="absolute left-1/2 top-[23%] -translate-x-1/2 flex items-center gap-1 whitespace-nowrap rounded-full bg-cluster/80 px-2 py-0.5 text-[clamp(0.55rem,0.9cqw,0.75rem)] font-semibold uppercase tracking-widest text-signal">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-signal" /> Live
          {detectorOffline && " · Detector indisponibil"}
        </span>
      )}
    </div>
  );
}
