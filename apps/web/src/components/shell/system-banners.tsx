import { useState } from "react";
import { PlugZap, WifiOff } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { notConnected } from "@/lib/not-connected";
import { useThread } from "@/stores/thread-store";
import { useUi } from "@/stores/ui-store";
import { useWorkspace } from "@/stores/workspace-store";

const DISMISS_KEY = "ugecy.notConnectedDismissed";
const wasDismissed = () => { try { return sessionStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; } };

export function SystemBanners() {
  const health = useWorkspace((s) => s.health);
  const modes = useWorkspace((s) => s.config?.modes);
  const missing = modes ? notConnected(modes) : [];
  const status = useThread((s) => s.status);
  const [dismissed, setDismissed] = useState(wasDismissed);
  const offline = health === "offline" || status === "offline";

  return (
    <div className="flex flex-col gap-2 empty:hidden [&:not(:empty)]:p-3 [&:not(:empty)]:pb-0">
      {offline && (
        <Alert variant="destructive" role="alert">
          <WifiOff />
          <AlertDescription className="flex flex-wrap items-center gap-2">
            Can't reach the Ugecy server. Retrying automatically.
            <Button size="sm" variant="outline" onClick={() => void useWorkspace.getState().ping()}>Retry now</Button>
          </AlertDescription>
        </Alert>
      )}
      {missing.length > 0 && !dismissed && (
        <Alert className="border-warning/30 bg-warning/12">
          <PlugZap className="text-warning" />
          <AlertDescription className="flex flex-col gap-1 text-foreground">
            <strong className="font-medium">Not connected</strong>
            <ul className="list-disc pl-4">
              {missing.map((m) => (
                <li key={m.key}>
                  {m.text}
                  {m.action === "device" && (
                    <Button size="sm" variant="link" className="h-auto px-1 py-0" onClick={() => useUi.getState().openInspector("device")}>Open Device tab</Button>
                  )}
                </li>
              ))}
            </ul>
            <Button size="sm" variant="ghost" className="w-fit" onClick={() => {
              setDismissed(true);
              try { sessionStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
            }}>Dismiss</Button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
