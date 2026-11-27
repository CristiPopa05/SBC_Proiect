import { useEffect, useState, type RefObject } from "react";
import { setDetectedSign } from "@/lib/sign-store";
import type { TrafficSignData } from "@/lib/signs";

const SAMPLE_INTERVAL_MS = 250;
const SIGN_HOLD_MS = 1_000;
const MAX_FRAME_SIZE = 640;

function sameSign(sign: TrafficSignData, other: TrafficSignData | null) {
  return sign.kind === other?.kind && sign.value === other.value;
}

export function useCameraDetection(videoRef: RefObject<HTMLVideoElement | null>, playing: boolean) {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    if (!playing) return;

    const controller = new AbortController();
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) {
      setOffline(true);
      return;
    }

    let timer: number;
    let lastSeen = 0;
    let previous: TrafficSignData | null = null;
    let confirmed: TrafficSignData | null = null;

    async function sample() {
      let delay = SAMPLE_INTERVAL_MS;
      try {
        const video = videoRef.current;
        if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;

        const scale = Math.min(1, MAX_FRAME_SIZE / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
        canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
        context!.drawImage(video, 0, 0, canvas.width, canvas.height);

        const frame = await new Promise<Blob | null>((resolve) =>
          canvas.toBlob(resolve, "image/jpeg", 0.82),
        );
        if (!frame || controller.signal.aborted) return;

        const response = await fetch("/api/detect", {
          method: "POST",
          body: frame,
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Detector unavailable");

        const { sign }: { sign: TrafficSignData | null } = await response.json();
        if (controller.signal.aborted) return;
        setOffline(false);
        const now = performance.now();
        if (sign && (sameSign(sign, previous) || sameSign(sign, confirmed))) {
          lastSeen = now;
          confirmed = sign;
          setDetectedSign(sign);
        } else if (now - lastSeen >= SIGN_HOLD_MS) {
          confirmed = null;
          setDetectedSign(null);
        }
        previous = sign;
      } catch {
        if (controller.signal.aborted) return;
        previous = null;
        confirmed = null;
        setOffline(true);
        setDetectedSign(null);
        delay = 1_000;
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(sample, delay);
      }
    }

    setOffline(false);
    setDetectedSign(null);
    void sample();
    return () => {
      controller.abort();
      window.clearTimeout(timer);
      setDetectedSign(null);
    };
  }, [playing, videoRef]);

  return offline;
}
