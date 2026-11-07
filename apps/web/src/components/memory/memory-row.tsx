import { Pencil } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { MemoryFile } from "@/types/agent";
import { timeAgo } from "../inspector/lib";

export function MemoryRow({ file, onSaved }: { file: MemoryFile; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(file.content);
  const [busy, setBusy] = useState(false);
  const readOnly = !file.editable || file.scope === "skills";

  const save = async () => {
    setBusy(true);
    try {
      await api.putMemory(file.path, draft);
      setEditing(false);
      onSaved();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save memory");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-col gap-1.5 rounded-lg border bg-card p-2.5">
      <div className="flex items-center gap-2">
        <span className="flex-1 truncate font-mono text-xs" title={file.path}>{file.path}</span>
        {readOnly && <Badge variant="secondary">SKILL</Badge>}
        {!readOnly && !editing && (
          <Button variant="ghost" size="icon-xs" aria-label={`Edit ${file.path}`} onClick={() => { setDraft(file.content); setEditing(true); }}>
            <Pencil />
          </Button>
        )}
      </div>
      {editing ? (
        <>
          <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={6} className="font-mono text-xs" aria-label={`Content of ${file.path}`} />
          <div className="flex justify-end gap-1">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
            <Button size="sm" disabled={busy || draft === file.content} onClick={save}>Save</Button>
          </div>
        </>
      ) : (
        <p className="line-clamp-4 whitespace-pre-wrap text-xs text-muted-foreground">{file.content}</p>
      )}
      {file.updated_at && <span className="text-[11px] text-muted-foreground">Updated {timeAgo(file.updated_at)}</span>}
    </li>
  );
}
