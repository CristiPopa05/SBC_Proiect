import { anchoredAngle, arcPath, polar } from "./dial-math";

const ANCHORS = [0, 20, 40, 60, 80, 100, 120, 150, 180, 220, 260];
const START = -140;
const END = 140;

export function Speedometer({
  speed,
  limit,
  children,
}: {
  speed: number;
  limit?: number | undefined;
  children?: React.ReactNode;
}) {
  const needle = anchoredAngle(speed, ANCHORS, START, END);
  const limitAngle = limit !== undefined ? anchoredAngle(limit, ANCHORS, START, END) : null;
  const minor: number[] = [];
  for (let i = 0; i < (ANCHORS.length - 1) * 4 + 1; i++) {
    minor.push(START + ((END - START) / ((ANCHORS.length - 1) * 4)) * i);
  }

  return (
    <div className="dial-ring relative aspect-square w-full rounded-full">
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full">
        <path d={arcPath(97, START, END)} stroke="var(--glow)" strokeWidth="2" fill="none" opacity="0.9" />
        <path d={arcPath(97, START, needle)} stroke="var(--glow)" strokeWidth="5" fill="none" />
        {minor.map((a, i) => {
          const major = i % 4 === 0;
          const [x0, y0] = polar(major ? 80 : 85, a);
          const [x1, y1] = polar(91, a);
          return (
            <line
              key={i}
              x1={x0}
              y1={y0}
              x2={x1}
              y2={y1}
              stroke="var(--dial-tick)"
              strokeWidth={major ? 2 : 1}
              opacity={major ? 1 : 0.55}
            />
          );
        })}
        {ANCHORS.slice(1).map((v, i) => {
          const a = START + ((END - START) / (ANCHORS.length - 1)) * (i + 1);
          const [x, y] = polar(68, a);
          return (
            <text
              key={v}
              x={x}
              y={y}
              textAnchor="middle"
              dominantBaseline="central"
              fill="var(--foreground)"
              fontFamily="var(--font-display)"
              fontWeight="600"
              fontSize="11"
            >
              {v}
            </text>
          );
        })}
        {limitAngle !== null && (
          <path
            d={arcPath(93, limitAngle - 2, limitAngle + 2)}
            stroke="var(--signal)"
            strokeWidth="7"
            fill="none"
          />
        )}
        <g transform={`rotate(${needle} 100 100)`} style={{ transition: "transform 600ms ease-out" }}>
          <line x1="100" y1="40" x2="100" y2="6" stroke="var(--foreground)" strokeWidth="2.5" strokeLinecap="round" />
        </g>
        <text x="58" y="160" fill="var(--muted-foreground)" fontSize="7" fontFamily="var(--font-display)">
          km/h
        </text>
      </svg>
      <div className="absolute inset-[24%] flex flex-col items-center justify-center text-center">
        {children}
      </div>
    </div>
  );
}
