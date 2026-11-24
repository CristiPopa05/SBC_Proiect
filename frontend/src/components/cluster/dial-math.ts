/** Angles in degrees: 0 = straight up, increasing clockwise. */
export function polar(r: number, deg: number, c = 100): [number, number] {
  const a = (deg * Math.PI) / 180;
  return [c + r * Math.sin(a), c - r * Math.cos(a)];
}

export function arcPath(r: number, from: number, to: number) {
  const [x0, y0] = polar(r, from);
  const [x1, y1] = polar(r, to);
  const large = Math.abs(to - from) > 180 ? 1 : 0;
  const sweep = to > from ? 1 : 0;
  return `M ${x0} ${y0} A ${r} ${r} 0 ${large} ${sweep} ${x1} ${y1}`;
}

/** Maps a value onto evenly spaced anchor labels (like real speedometers). */
export function anchoredAngle(value: number, anchors: number[], start: number, end: number) {
  const step = (end - start) / (anchors.length - 1);
  const first = anchors[0] ?? 0;
  if (value <= first) return start;
  for (let i = 1; i < anchors.length; i++) {
    const lo = anchors[i - 1] ?? 0;
    const hi = anchors[i] ?? 0;
    if (value <= hi) return start + step * (i - 1 + (value - lo) / (hi - lo));
  }
  return end;
}
