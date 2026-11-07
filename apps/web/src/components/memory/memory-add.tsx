import { Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { slugify } from "../inspector/lib";

export function MemoryAdd({ onAdded }: { onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const slug = slugify(title);

  if (!open) return <Button variant="outline" size="sm" className="w-fit" onClick={() => setOpen(true)}><Plus />Add memory</Button>;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.putMemory(`/memories/${slug}.md`, content);
      setTitle(""); setContent(""); setOpen(false);
      onAdded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add memory");
    }
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 rounded-lg border p-2.5">
      <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Name, e.g. Brand voice" aria-label="Memory name" />
      <p className="font-mono text-[11px] text-muted-foreground">/memories/{slug || "…"}.md</p>
      <Textarea value={content} onChange={(e) => setContent(e.target.value)} rows={4} placeholder="Brand rules, preferences, do and don't…" aria-label="Memory content" />
      <div className="flex justify-end gap-1">
        <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
        <Button type="submit" size="sm" disabled={!slug || !content.trim()}>Save</Button>
      </div>
    </form>
  );
}
