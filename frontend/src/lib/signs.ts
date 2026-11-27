export type SignKind =
  | "speed"
  | "stop"
  | "red_light"
  | "green_light"
  | "yield"
  | "no_entry"
  | "no_overtaking"
  | "parking"
  | "no_parking"
  | "priority"
  | "oncoming_has_priority"
  | "priority_over_oncoming"
  | "pedestrian"
  | "roundabout"
  | "warning"
  | "gtsrb";

export interface TrafficSignData {
  kind: SignKind;
  /** Speed in km/h or the original GTSRB class ID. */
  value?: number;
  label?: string;
  image?: string;
}

export function signLabel(sign: TrafficSignData): string {
  switch (sign.kind) {
    case "speed":
      return `Limită ${sign.value ?? "?"} km/h`;
    case "stop":
      return "Stop";
    case "red_light":
      return "Semafor roșu";
    case "green_light":
      return "Semafor verde";
    case "yield":
      return "Cedează trecerea";
    case "no_entry":
      return "Accesul interzis";
    case "no_overtaking":
      return "Depășirea interzisă";
    case "parking":
      return "Parcare";
    case "no_parking":
      return "Parcarea interzisă";
    case "priority":
      return "Drum cu prioritate";
    case "oncoming_has_priority":
      return "Prioritate pentru circulația din sens invers";
    case "priority_over_oncoming":
      return "Prioritate față de circulația din sens invers";
    case "pedestrian":
      return "Trecere pietoni";
    case "roundabout":
      return "Sens giratoriu";
    case "warning":
      return "Atenție";
    case "gtsrb":
      return sign.label ?? "Indicator rutier";
  }
}

export const DEMO_SIGNS: TrafficSignData[] = [
  { kind: "speed", value: 30 },
  { kind: "speed", value: 50 },
  { kind: "speed", value: 90 },
  { kind: "speed", value: 130 },
  { kind: "stop" },
  { kind: "yield" },
  { kind: "no_entry" },
  { kind: "no_overtaking" },
  { kind: "parking" },
  { kind: "no_parking" },
  { kind: "priority" },
  { kind: "pedestrian" },
  { kind: "roundabout" },
  { kind: "warning" },
];
