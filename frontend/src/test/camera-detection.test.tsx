import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useCameraDetection } from "@/hooks/use-camera-detection";
import { setDetectedSign } from "@/lib/sign-store";
import type { TrafficSignData } from "@/lib/signs";

vi.mock("@/lib/sign-store", () => ({ setDetectedSign: vi.fn() }));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Camera detection", () => {
  it("confirms a sign across frames and ignores a single conflicting prediction", async () => {
    vi.useFakeTimers();
    const limit50 = { kind: "speed", value: 50 } as const;
    const signs: (TrafficSignData | null)[] = [
      { kind: "stop" },
      null,
      { kind: "speed", value: 30 },
      limit50,
      limit50,
      { kind: "stop" },
    ];
    vi.stubGlobal("fetch", async () => ({
      ok: true,
      json: async () => ({ sign: signs.shift() ?? null }),
    }));
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((callback) => {
      callback(new Blob([], { type: "image/jpeg" }));
    });

    const video = document.createElement("video");
    Object.defineProperties(video, {
      readyState: { value: HTMLMediaElement.HAVE_CURRENT_DATA },
      videoWidth: { value: 640 },
      videoHeight: { value: 480 },
    });
    const videoRef = { current: video };
    await act(async () => {
      renderHook(() => useCameraDetection(videoRef, true));
    });

    await act(() => vi.advanceTimersByTimeAsync(750));
    expect(setDetectedSign).toHaveBeenCalledExactlyOnceWith(null);

    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(setDetectedSign).toHaveBeenCalledTimes(2);
    expect(setDetectedSign).toHaveBeenLastCalledWith(limit50);

    await act(() => vi.advanceTimersByTimeAsync(750));
    expect(setDetectedSign).toHaveBeenLastCalledWith(null);
  });
});
