import { createFileRoute } from "@tanstack/react-router";
import { Dashboard } from "@/components/cluster/Dashboard";
import { TrafficSign } from "@/components/cluster/TrafficSign";
import { DEMO_SIGNS, signLabel } from "@/lib/signs";
import { setDetectedSign } from "@/lib/sign-store";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sign Assist — Bord digital cu cameră" },
      {
        name: "description",
        content: "Bord digital de mașină cu cameră live și afișarea semnelor de circulație recunoscute.",
      },
      { property: "og:title", content: "Sign Assist — Bord digital cu cameră" },
      {
        property: "og:description",
        content: "Arată un indicator rutier la cameră și vezi-l pe bord, ca la mașinile moderne.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-background px-4 py-10">
      <div className="w-full max-w-6xl">
        <Dashboard />
      </div>

      <section className="w-full max-w-6xl">
        <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-muted-foreground">
          Testează afișarea semnelor
        </h2>
        <div className="mt-4 flex flex-wrap gap-3">
          {DEMO_SIGNS.map((s) => (
            <button
              key={`${s.kind}-${s.value ?? ""}`}
              onClick={() => setDetectedSign(s)}
              title={signLabel(s)}
              aria-label={signLabel(s)}
              className="rounded-lg border border-border bg-card p-2 transition-colors hover:border-primary"
            >
              <TrafficSign sign={s} className="h-10 w-10" />
            </button>
          ))}
          <button
            onClick={() => setDetectedSign(null)}
            className="rounded-lg border border-border bg-card px-4 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
          >
            Golește
          </button>
        </div>
      </section>
    </main>
  );
}
