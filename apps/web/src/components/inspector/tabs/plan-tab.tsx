import { Check, ChevronRight, Circle, ListTodo, Loader2 } from "lucide-react";
import { useMemo } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Progress } from "@/components/ui/progress";
import { useThread } from "@/stores/thread-store";
import type { Todo } from "@/types/agent";
import { EmptyState } from "../empty";

function Row({ todo }: { todo: Todo }) {
  const done = todo.status === "completed";
  return (
    <li className="flex items-start gap-2 rounded-md px-2 py-1.5 text-[13px]">
      {done ? <Check className="mt-0.5 size-3.5 shrink-0 text-success" aria-label="Completed" />
        : todo.status === "in_progress" ? <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin text-primary" aria-label="In progress" />
        : <Circle className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-label="Pending" />}
      <span className={done ? "text-muted-foreground line-through" : ""}>{todo.content}</span>
    </li>
  );
}

export default function PlanTab() {
  const todos = useThread((s) => s.todos);
  const { open, done } = useMemo(() => ({
    open: todos.filter((t) => t.status !== "completed"),
    done: todos.filter((t) => t.status === "completed"),
  }), [todos]);
  if (!todos.length) return <EmptyState icon={ListTodo}>No plan yet. Ugecy writes one for multi-step work.</EmptyState>;
  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex flex-col gap-1.5">
        <p className="text-sm font-semibold tabular-nums">{done.length} of {todos.length}</p>
        <Progress value={(done.length / todos.length) * 100} aria-label="Plan progress" />
      </div>
      <Collapsible defaultOpen>
        <CollapsibleTrigger className="group flex w-full items-center gap-1 text-xs font-medium text-muted-foreground">
          <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />To do ({open.length})
        </CollapsibleTrigger>
        <CollapsibleContent><ul className="mt-1 flex flex-col gap-1">{open.map((t, i) => <Row key={i} todo={t} />)}</ul></CollapsibleContent>
      </Collapsible>
      {done.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="group flex w-full items-center gap-1 text-xs font-medium text-muted-foreground">
            <ChevronRight className="size-3.5 transition-transform group-data-[state=open]:rotate-90" />Completed ({done.length})
          </CollapsibleTrigger>
          <CollapsibleContent><ul className="mt-1 flex flex-col gap-1">{done.map((t, i) => <Row key={i} todo={t} />)}</ul></CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
}
