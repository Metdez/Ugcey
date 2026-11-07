import { FolderTree } from "lucide-react";
import { useEffect, useState } from "react";
import { FileTree } from "@/components/files/file-tree";
import { FileViewer } from "@/components/files/file-viewer";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { EmptyState } from "../empty";

export default function FilesTab() {
  const files = useThread((s) => s.files);
  const threadId = useThread((s) => s.threadId);
  const focusPath = useUi((s) => (s.focus?.kind === "file" ? s.focus.id : null));
  const [selected, setSelected] = useState<string | null>(null);
  useEffect(() => { if (focusPath) setSelected(focusPath); }, [focusPath]);

  if (!files.length) return <EmptyState icon={FolderTree}>Research notes, briefs and scripts the agent writes appear here.</EmptyState>;
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <FileTree files={files} selected={selected} onSelect={setSelected} />
      {selected && threadId && (
        <div className="flex min-h-0 flex-1 flex-col border-t pt-3">
          <FileViewer threadId={threadId} path={selected} />
        </div>
      )}
    </div>
  );
}
