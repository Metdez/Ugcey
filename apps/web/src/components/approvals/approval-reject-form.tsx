import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Textarea } from "@/components/ui/textarea";

export const REJECT_REASONS = ["Off-brand", "Unsupported claim", "Missing #ad disclosure", "Wrong account", "Bad timing"];

export function ApprovalRejectForm(props: { reason: string; onReason: (v: string) => void; text: string; onText: (v: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <ToggleGroup type="single" variant="outline" size="sm" className="flex-wrap justify-start" value={props.reason}
        onValueChange={props.onReason} aria-label="Reject reason">
        {REJECT_REASONS.map((r) => <ToggleGroupItem key={r} value={r} className="text-xs">{r}</ToggleGroupItem>)}
      </ToggleGroup>
      <Textarea rows={2} placeholder="Add a note (optional)" aria-label="Reject note" value={props.text} onChange={(e) => props.onText(e.target.value)} />
    </div>
  );
}
