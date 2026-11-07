import { Circle, CircleCheck, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";

export function InlinePlanCard() {
  const todos = useThread((s) => s.todos);
  const setTab = useUi((s) => s.openInspector);
  if (!todos.length) return null;
  const done = todos.filter((t) => t.status === "completed").length;
  const current = todos.find((t) => t.status === "in_progress");
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">Plan · {done}/{todos.length} done</span>
        <Button variant="ghost" size="xs" onClick={() => setTab("plan")}>Open Plan</Button>
      </div>
      <Progress value={(done / todos.length) * 100} className="my-2 h-1" aria-label="Plan progress" />
      <ul className="flex flex-col gap-1 text-[13px]">
        {todos.map((t, i) => (
          <li key={i} className={t === current ? "flex items-center gap-2 text-foreground" : "flex items-center gap-2 text-muted-foreground"}>
            {t.status === "completed" ? <CircleCheck className="size-3.5 text-success" />
              : t.status === "in_progress" ? <Loader2 className="size-3.5 animate-spin" /> : <Circle className="size-3.5" />}
            <span className={t.status === "completed" ? "line-through" : ""}>{t.content}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
