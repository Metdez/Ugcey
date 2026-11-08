import { useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { dropbox, type DropboxStatus } from "@/lib/dropbox";

interface Props { open: boolean; onOpenChange: (o: boolean) => void; status: DropboxStatus | null; onStatus: (s: DropboxStatus) => void }

export function DropboxConnect({ open, onOpenChange, status, onStatus }: Props) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try { await fn(); } catch (e) { toast.error(e instanceof Error ? e.message : "Dropbox request failed"); } finally { setBusy(false); }
  };
  const openDropbox = () => run(async () => { window.open(await dropbox.connect(), "_blank"); });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      onStatus(await dropbox.submitCode(code.trim()));
      setCode("");
      toast.success("Dropbox connected — copying your media");
      void dropbox.backfill().catch(() => {});
      onOpenChange(false);
    });
  };
  const disconnect = () => run(async () => { onStatus(await dropbox.disconnect()); toast.success("Dropbox disconnected"); });
  const missing = status?.missing_scopes ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Dropbox</DialogTitle>
          <DialogDescription>Generated and uploaded media is copied into your Dropbox.</DialogDescription>
        </DialogHeader>
        {status && !status.configured ? (
          <p className="text-sm text-muted-foreground">Dropbox app keys are not set on the server.</p>
        ) : status?.connected ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm">Connected as <span className="font-medium">{status.account_name ?? "your account"}</span>{status.email && <span className="text-muted-foreground"> ({status.email})</span>}</p>
            {missing.length > 0 && (
              <Alert variant="destructive">
                <AlertTitle>Missing permissions: {missing.join(", ")}</AlertTitle>
                <AlertDescription>In the Dropbox App Console → your app → Permissions, tick these, click Submit, then Disconnect and connect again.</AlertDescription>
              </Alert>
            )}
            <Button variant="outline" className="w-fit" onClick={disconnect} disabled={busy}>Disconnect</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <p className="text-sm font-medium">1. Approve access</p>
              <Button type="button" variant="outline" className="w-fit" onClick={openDropbox} disabled={busy}>Open Dropbox</Button>
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="text-sm font-medium">2. Paste the code Dropbox shows</p>
              <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Access code" aria-label="Dropbox access code" autoComplete="off" />
            </div>
            <Button type="submit" className="w-fit" disabled={busy || !code.trim()}>Connect</Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
