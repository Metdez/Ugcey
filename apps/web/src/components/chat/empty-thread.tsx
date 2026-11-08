import { useEffect, useState } from "react";
import { BarChart3, CalendarClock, Clapperboard, PenLine, Search, Shapes, type LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import { threadActions } from "@/stores/thread-store";

const STARTERS: Array<{ icon: LucideIcon; title: string; prompt: string }> = [
  { icon: Search, title: "Find winning hooks", prompt: "Find the top 20 TikTok UGC hooks for clean skincare this month and explain why they work." },
  { icon: Shapes, title: "Extract patterns", prompt: "Break these 5 videos into hook, script structure and CTA patterns." },
  { icon: PenLine, title: "Write scripts", prompt: "Write 5 original 30-second UGC scripts for our serum using the top patterns." },
  { icon: Clapperboard, title: "Generate media", prompt: "Generate 3 vertical UGC-style videos for script #2." },
  { icon: CalendarClock, title: "Schedule posts", prompt: "Schedule the approved videos to @glowco on TikTok and Instagram this week." },
  { icon: BarChart3, title: "Review performance", prompt: "How did last week's posts perform? What should we make next?" },
];

export function EmptyThread() {
  const [prompts, setPrompts] = useState<string[] | null>(null);
  useEffect(() => {
    api.getConfig().then((c) => { if (c.starter_prompts?.length) setPrompts(c.starter_prompts.slice(0, 6)); }).catch(() => {});
  }, []);
  const items = STARTERS.map((s, i) => ({ ...s, prompt: prompts?.[i] ?? s.prompt }));
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-10">
      <h1 className="text-[28px] leading-[34px] font-semibold tracking-[-0.02em]">What are we making today?</h1>
      <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(({ icon: Icon, title, prompt }) => (
          <button key={title} type="button" onClick={() => void threadActions.send(prompt)}
            className="flex flex-col gap-1 rounded-lg border bg-card p-3 text-left transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
            <Icon className="size-4 text-primary" aria-hidden />
            <span className="text-sm font-semibold">{title}</span>
            <span className="line-clamp-2 text-xs text-muted-foreground">{prompt}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
