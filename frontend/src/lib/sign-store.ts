import { useSyncExternalStore } from "react";
import type { TrafficSignData } from "./signs";

/**
 * Integration point for sign recognition: call setDetectedSign() with the
 * sign the AI recognized and the dashboard shows it in the sign slot.
 */
interface SignState {
  current: TrafficSignData | null;
  history: TrafficSignData[];
}

const HISTORY_SIZE = 4;
let state: SignState = { current: null, history: [] };
const listeners = new Set<() => void>();
const serverSnapshot: SignState = state;

export function setDetectedSign(sign: TrafficSignData | null) {
  if (state.current?.kind === sign?.kind && state.current?.value === sign?.value) return;
  const history = state.current
    ? [state.current, ...state.history].slice(0, HISTORY_SIZE)
    : state.history;
  state = { current: sign, history };
  listeners.forEach((l) => l());
}

export function getSignState() {
  return state;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDetectedSign() {
  return useSyncExternalStore(subscribe, getSignState, () => serverSnapshot);
}
