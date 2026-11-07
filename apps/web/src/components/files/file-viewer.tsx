import { Check, Copy, Download } from "lucide-react";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { copy, download } from "../inspector/hooks";
import { isMarkdown } from "../inspector/lib";

export function FileViewer({ threadId, path }: { threadId: string; path: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    let live = true;
    setContent(null);
    setError(null);
    api.getFile(threadId, path)
      .then((f) => live && setContent(f.content))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Could not load file"));
    return () => { live = false; };
  }, [threadId, path]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <div className="flex items-center gap-1">
        <span className="flex-1 truncate font-mono text-xs" title={path}>{path}</span>
        <Button variant="ghost" size="icon-sm" aria-label="Copy file" disabled={content === null}
          onClick={() => { void copy(content ?? ""); setCopied(true); setTimeout(() => setCopied(false), 1200); }}>
          {copied ? <Check /> : <Copy />}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Download file" disabled={content === null}
          onClick={() => download(path.split("/").pop() || "file.txt", content ?? "")}>
          <Download />
        </Button>
      </div>
      {error ? <p className="text-xs text-destructive" role="alert">{error}</p>
        : content === null ? <p className="text-xs text-muted-foreground">Loading…</p>
        : isMarkdown(path) ? (
          <div className="text-[13px] leading-relaxed [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mb-1 [&_h2]:mt-3 [&_h2]:text-sm [&_h2]:font-semibold [&_li]:ml-4 [&_li]:list-disc [&_p]:my-1.5 [&_table]:text-xs [&_td]:border [&_td]:px-1.5 [&_th]:border [&_th]:px-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        ) : <pre className="overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted p-2 font-mono text-[12.5px] leading-[1.6]">{content}</pre>}
    </div>
  );
}
