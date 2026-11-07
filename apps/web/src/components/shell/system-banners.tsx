import { useState, type FormEvent } from "react";
import { FlaskConical, Lock, WifiOff } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useThread } from "@/stores/thread-store";
import { useWorkspace } from "@/stores/workspace-store";

const MOCK_KEY = "ugecy.mockBannerDismissed";
const wasDismissed = () => { try { return sessionStorage.getItem(MOCK_KEY) === "1"; } catch { return false; } };

function UnlockForm() {
  const [key, setKey] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (key.trim()) location.href = `/api/edge/unlock?key=${encodeURIComponent(key.trim())}`;
  };
  return (
    <form onSubmit={submit} className="mt-2 flex max-w-sm gap-2">
      <Input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)}
        placeholder="Access key" aria-label="Access key" className="h-8" />
      <Button type="submit" size="sm" disabled={!key.trim()}>Unlock</Button>
    </form>
  );
}

export function SystemBanners() {
  const health = useWorkspace((s) => s.health);
  const mock = useWorkspace((s) => !!s.config && Object.values(s.config.modes).includes("mock"));
  const status = useThread((s) => s.status);
  const [dismissed, setDismissed] = useState(wasDismissed);
  const locked = health === "locked" || status === "locked";
  const offline = !locked && (health === "offline" || status === "offline");

  return (
    <div className="flex flex-col gap-2 empty:hidden [&:not(:empty)]:p-3 [&:not(:empty)]:pb-0">
      {locked && (
        <Alert className="border-warning/30 bg-warning/12 text-warning">
          <Lock />
          <AlertDescription className="text-foreground">
            This workspace is locked. Enter the access key to continue.
            <UnlockForm />
          </AlertDescription>
        </Alert>
      )}
      {offline && (
        <Alert variant="destructive" role="alert">
          <WifiOff />
          <AlertDescription className="flex flex-wrap items-center gap-2">
            Can't reach the Ugecy server. Retrying automatically.
            <Button size="sm" variant="outline" onClick={() => void useWorkspace.getState().ping()}>Retry now</Button>
          </AlertDescription>
        </Alert>
      )}
      {mock && !dismissed && (
        <Alert className="border-warning/30 bg-warning/12">
          <FlaskConical className="text-warning" />
          <AlertDescription className="flex flex-wrap items-center gap-2 text-foreground">
            Mock mode: media and publishing are simulated. Nothing will be posted.
            <Button size="sm" variant="ghost" onClick={() => {
              setDismissed(true);
              try { sessionStorage.setItem(MOCK_KEY, "1"); } catch { /* ignore */ }
            }}>Dismiss</Button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
