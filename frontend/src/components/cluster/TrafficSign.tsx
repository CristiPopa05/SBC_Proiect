import type { TrafficSignData } from "@/lib/signs";

const C = {
  red: "var(--sign-red)",
  blue: "var(--sign-blue)",
  yellow: "var(--sign-yellow)",
  white: "var(--sign-white)",
  ink: "var(--sign-ink)",
};

export function TrafficSign({ sign, className }: { sign: TrafficSignData; className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label={sign.kind}>
      <SignShape sign={sign} />
    </svg>
  );
}

function SignShape({ sign }: { sign: TrafficSignData }) {
  switch (sign.kind) {
    case "speed": {
      const v = String(sign.value ?? "");
      return (
        <>
          <circle cx="50" cy="50" r="46" fill={C.white} />
          <circle cx="50" cy="50" r="40" fill="none" stroke={C.red} strokeWidth="11" />
          <text
            x="50"
            y="51"
            textAnchor="middle"
            dominantBaseline="central"
            fontFamily="var(--font-display)"
            fontWeight="700"
            fontSize={v.length > 2 ? 34 : 42}
            fill={C.ink}
          >
            {v}
          </text>
        </>
      );
    }
    case "stop":
      return (
        <>
          <polygon
            points="30,4 70,4 96,30 96,70 70,96 30,96 4,70 4,30"
            fill={C.red}
            stroke={C.white}
            strokeWidth="4"
          />
          <text
            x="50"
            y="51"
            textAnchor="middle"
            dominantBaseline="central"
            fontFamily="var(--font-display)"
            fontWeight="700"
            fontSize="28"
            fill={C.white}
          >
            STOP
          </text>
        </>
      );
    case "red_light":
    case "green_light":
      return (
        <>
          <rect x="29" y="2" width="42" height="96" rx="9" fill={C.ink} stroke={C.white} />
          <circle cx="50" cy="23" r="11" fill={sign.kind === "red_light" ? C.red : "#414952"} />
          <circle cx="50" cy="50" r="11" fill="#414952" />
          <circle cx="50" cy="77" r="11" fill={sign.kind === "green_light" ? "var(--eco)" : "#414952"} />
        </>
      );
    case "yield":
      return (
        <>
          <polygon points="4,10 96,10 50,92" fill={C.red} />
          <polygon points="22,21 78,21 50,70" fill={C.white} />
        </>
      );
    case "no_entry":
      return (
        <>
          <circle cx="50" cy="50" r="46" fill={C.red} />
          <rect x="18" y="41" width="64" height="18" rx="2" fill={C.white} />
        </>
      );
    case "no_overtaking":
      return (
        <>
          <circle cx="50" cy="50" r="46" fill={C.white} />
          <circle cx="50" cy="50" r="40" fill="none" stroke={C.red} strokeWidth="11" />
          <Car x={26} fill={C.red} />
          <Car x={52} fill={C.ink} />
        </>
      );
    case "no_parking":
      return (
        <>
          <circle cx="50" cy="50" r="46" fill={C.red} />
          <circle cx="50" cy="50" r="36" fill={C.blue} />
          <line x1="24" y1="24" x2="76" y2="76" stroke={C.red} strokeWidth="10" />
        </>
      );
    case "priority":
      return (
        <>
          <polygon points="50,3 97,50 50,97 3,50" fill={C.white} stroke={C.ink} strokeWidth="1.5" />
          <polygon points="50,18 82,50 50,82 18,50" fill={C.yellow} />
        </>
      );
    case "pedestrian":
      return (
        <>
          <rect x="4" y="4" width="92" height="92" rx="8" fill={C.blue} />
          <polygon points="50,14 88,82 12,82" fill={C.white} />
          <circle cx="52" cy="38" r="5" fill={C.ink} />
          <path
            d="M50 45 L46 60 L40 72 M46 60 L54 72 M48 50 L58 56 M48 50 L40 56"
            stroke={C.ink}
            strokeWidth="4"
            strokeLinecap="round"
            fill="none"
          />
          <path d="M28 78 H72" stroke={C.ink} strokeWidth="3" strokeDasharray="5 3" />
        </>
      );
    case "roundabout":
      return (
        <>
          <circle cx="50" cy="50" r="46" fill={C.blue} />
          {[0, 120, 240].map((r) => (
            <g key={r} transform={`rotate(${r} 50 50)`}>
              <path
                d="M50 22 A28 28 0 0 1 74 36"
                stroke={C.white}
                strokeWidth="8"
                fill="none"
              />
              <polygon points="70,26 82,40 66,44" fill={C.white} />
            </g>
          ))}
        </>
      );
    case "warning":
      return (
        <>
          <polygon points="50,6 96,88 4,88" fill={C.red} strokeLinejoin="round" />
          <polygon points="50,24 81,79 19,79" fill={C.white} />
          <rect x="46" y="40" width="8" height="24" rx="2" fill={C.ink} />
          <circle cx="50" cy="71" r="4.5" fill={C.ink} />
        </>
      );
  }
}

function Car({ x, fill }: { x: number; fill: string }) {
  return (
    <g transform={`translate(${x} 34)`}>
      <rect x="2" y="0" width="18" height="10" rx="3" fill={fill} />
      <rect x="0" y="8" width="22" height="18" rx="3" fill={fill} />
      <rect x="1" y="24" width="5" height="6" rx="1" fill={fill} />
      <rect x="16" y="24" width="5" height="6" rx="1" fill={fill} />
    </g>
  );
}
