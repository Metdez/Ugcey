import { Button } from "@/components/ui/button";
import { threadActions } from "@/stores/thread-store";

export function TurnError({ message, retryable, lastUserText }: { message: string; retryable: boolean; lastUserText: string | null }) {
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-lg border border-destructive/40 bg-destructive/12 p-3 text-sm">
      <span>The run stopped: {message}</span>
      <span className="flex gap-1">
        {retryable && lastUserText && <Button size="sm" variant="outline" onClick={() => void threadActions.send(lastUserText)}>Retry</Button>}
        <Button size="sm" variant="ghost" onClick={() => void navigator.clipboard?.writeText(message)}>Copy details</Button>
      </span>
    </div>
  );
}
