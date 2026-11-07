import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ApprovalRequest } from "@/types/agent";

export type Draft = Record<string, string | boolean>;

export const initialDraft = (r: ApprovalRequest): Draft =>
  Object.fromEntries(Object.entries(r.args).map(([k, v]) => [k,
    typeof v === "boolean" ? v : v !== null && typeof v === "object" ? JSON.stringify(v, null, 2) : String(v ?? "")]));

export function ApprovalEditForm(props: {
  request: ApprovalRequest; idx: number; draft: Draft; errors: Record<string, string>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {Object.entries(props.request.args).map(([k, orig]) => {
        const id = `ap-${props.idx}-${k}`;
        const err = props.errors[`${props.idx}.${k}`];
        const v = props.draft[k];
        return (
          <div key={k} className="flex flex-col gap-1">
            <Label htmlFor={id} className="font-mono text-xs">{k}</Label>
            {typeof orig === "boolean" ? (
              <Switch id={id} checked={Boolean(v)} onCheckedChange={(c) => props.onChange(k, c)} />
            ) : typeof orig === "number" ? (
              <Input id={id} inputMode="decimal" value={String(v)} aria-invalid={!!err} onChange={(e) => props.onChange(k, e.target.value)} />
            ) : (
              <Textarea id={id} rows={orig !== null && typeof orig === "object" ? 4 : 2} value={String(v)} aria-invalid={!!err}
                className={orig !== null && typeof orig === "object" ? "font-mono text-xs" : ""}
                onChange={(e) => props.onChange(k, e.target.value)} />
            )}
            {err && <p role="alert" className="text-xs text-destructive">{err}</p>}
          </div>
        );
      })}
    </div>
  );
}
