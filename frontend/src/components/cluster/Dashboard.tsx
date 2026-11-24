import { useEffect, useState } from "react";
import { CircleParking, Leaf, PlugZap, TriangleAlert, Car, Gauge } from "lucide-react";
import { CameraDial } from "./CameraDial";
import { Speedometer } from "./Speedometer";
import { TrafficSign } from "./TrafficSign";
import { useDetectedSign } from "@/lib/sign-store";
import { signLabel } from "@/lib/signs";

function useClock() {
  const [time, setTime] = useState("--:--");
  useEffect(() => {
    const tick = () =>
      setTime(new Date().toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" }));
    tick();
    const id = setInterval(tick, 10_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

export function Dashboard() {
  const { current, history } = useDetectedSign();
  const time = useClock();
  const limit = current?.kind === "speed" ? current.value : undefined;
  const signKey = current ? `${current.kind}-${current.value ?? ""}` : "none";

  return (
    <div className="@container w-full">
      <div className="cluster-panel relative overflow-hidden rounded-[3cqw] px-[3cqw] pb-[2cqw] pt-[1.6cqw]">
        {/* top bar */}
        <div className="grid grid-cols-[1fr_0.75fr_1fr] items-center text-[1.6cqw] font-semibold tabular-nums">
          <span className="pl-[34%] text-foreground">{time}</span>
          <span />
          <span className="pl-[30%] text-foreground">19.5 °C</span>
        </div>

        <div className="mt-[0.6cqw] grid grid-cols-[1fr_0.75fr_1fr] items-center gap-[2cqw]">
          <CameraDial />

          {/* center column */}
          <div className="flex flex-col items-center gap-[2.4cqw]">
            <div className="flex w-full items-center justify-center gap-[2.6cqw]">
              <div className="flex flex-col items-center text-muted-foreground">
                <Car className="h-[2.4cqw] w-[2.4cqw]" />
              </div>
              <div className="flex flex-col items-center text-muted-foreground">
                <Gauge className="h-[2.4cqw] w-[2.4cqw]" />
                <span className="text-[1.1cqw] font-semibold">{limit ?? "--"}</span>
              </div>

              <div className="text-center">
                <div className="font-display text-[7cqw] font-semibold leading-none text-foreground">0</div>
                <div className="text-[1.3cqw] text-muted-foreground">km/h</div>
              </div>

              {/* Sign slot — the recognized sign appears here */}
              <div
                className="sign-slot flex h-[6.5cqw] w-[6.5cqw] items-center justify-center"
                aria-live="polite"
              >
                {current ? (
                  <TrafficSign key={signKey} sign={current} className="sign-pop h-full w-full" />
                ) : (
                  <div className="h-full w-full rounded-full border-2 border-dashed border-border" />
                )}
              </div>
            </div>

            <div className="text-center">
              <div className="text-[1.2cqw] uppercase tracking-[0.3em] text-muted-foreground">
                Semn detectat
              </div>
              <div className="text-[1.8cqw] font-semibold text-foreground">
                {current ? signLabel(current) : "—"}
              </div>
            </div>
          </div>

          <Speedometer speed={0} limit={limit}>
            <div className="text-[1cqw] uppercase tracking-[0.3em] text-muted-foreground">
              Ultimele semne
            </div>
            <div className="mt-[1cqw] flex min-h-[4cqw] items-center justify-center gap-[0.8cqw]">
              {history.length === 0 ? (
                <span className="text-[1.1cqw] text-muted-foreground">Niciunul încă</span>
              ) : (
                history.map((s, i) => (
                  <TrafficSign
                    key={i}
                    sign={s}
                    className="h-[3.4cqw] w-[3.4cqw]"
                  />
                ))
              )}
            </div>
            <div className="mt-[1cqw] h-px w-3/4 bg-border" />
            <div className="mt-[0.8cqw] text-[1.6cqw] font-semibold uppercase tracking-widest text-foreground">
              Sign Assist
            </div>
          </Speedometer>
        </div>

        {/* bottom bar */}
        <div className="mt-[1cqw] grid grid-cols-[1fr_0.75fr_1fr] items-center text-[1.3cqw] text-muted-foreground">
          <div className="flex items-center gap-[1.5cqw] pl-[6%]">
            <Leaf className="h-[2cqw] w-[2cqw]" />
            <span className="flex flex-col items-center">
              <CircleParking className="h-[2cqw] w-[2cqw] text-signal" />
            </span>
            <span className="flex flex-col items-center font-semibold text-foreground">
              BOOST
              <span className="mt-0.5 flex gap-0.5">
                {[0, 1, 2, 3, 4].map((i) => (
                  <span key={i} className="h-[0.5cqw] w-[0.8cqw] rounded-sm bg-muted-foreground" />
                ))}
              </span>
            </span>
          </div>
          <div className="mx-auto h-[0.4cqw] w-2/3 rounded-full bg-muted" />
          <div className="flex items-center justify-end gap-[1.5cqw] pr-[8%]">
            <PlugZap className="h-[2cqw] w-[2cqw]" />
            <span className="text-[1.8cqw] font-semibold text-foreground">
              233 <span className="text-[1.2cqw] text-muted-foreground">km</span>
            </span>
            <TriangleAlert className="h-[2cqw] w-[2cqw]" />
          </div>
        </div>
      </div>
    </div>
  );
}
