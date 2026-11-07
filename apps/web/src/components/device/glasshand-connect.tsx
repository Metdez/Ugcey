import { AlertTriangle, ExternalLink, Loader2, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCountdown, type GlasshandStatus } from "@/lib/glasshand";

interface Props { status: GlasshandStatus | null; busy: boolean; error: string | null; onConnect: () => void; onCancel: () => void }

export function GlasshandDisconnected({ busy, error, onConnect }: Pick<Props, "busy" | "error" | "onConnect">) {
  return (
    <Card className="gap-3 py-4">
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><Smartphone className="size-4" aria-hidden />Connect your Glasshand iPhone</CardTitle>
        <CardDescription>
          Glasshand rents a real iPhone you can watch live here. You approve access with an email code on Glasshand&apos;s site,
          and the access tokens stay on the server, never in your browser.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
        <Button onClick={onConnect} disabled={busy}>{busy && <Loader2 className="animate-spin" aria-hidden />}Connect Glasshand</Button>
      </CardContent>
    </Card>
  );
}

export function GlasshandPending({ status, busy, onCancel }: Pick<Props, "status" | "busy" | "onCancel">) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const url = status?.verification_uri_complete ?? status?.verification_uri;
  return (
    <Card className="gap-3 py-4">
      <CardHeader>
        <CardTitle>Approve Glasshand access</CardTitle>
        <CardDescription>Open the approval page and confirm this code. Glasshand emails you a verification code.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-3">
        <p className="select-all font-mono text-3xl font-semibold tracking-[0.25em]" aria-label="Approval code">{status?.user_code ?? "…"}</p>
        {url && (
          <Button asChild>
            <a href={url} target="_blank" rel="noopener noreferrer">Open approval page<ExternalLink aria-hidden /></a>
          </Button>
        )}
        <p className="flex flex-col items-center gap-0.5 text-xs text-muted-foreground" role="status">
          <span className="flex items-center gap-1.5"><Loader2 className="size-3 animate-spin" aria-hidden />Waiting for approval…</span>
          <span className="tabular-nums">Code expires in {formatCountdown(status?.expires_at, now)}</span>
        </p>
        <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>Cancel</Button>
      </CardContent>
    </Card>
  );
}

export function GlasshandFailed({ status, busy, onConnect }: Pick<Props, "status" | "busy" | "onConnect">) {
  const title = status?.state === "denied" ? "Access denied" : status?.state === "expired" ? "Approval code expired" : "Glasshand error";
  return (
    <Alert variant="destructive">
      <AlertTriangle aria-hidden />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>
        <p>{status?.message ?? "Glasshand access was not approved. You can try again."}</p>
        <Button size="sm" variant="outline" className="mt-2" onClick={onConnect} disabled={busy}>Try again</Button>
      </AlertDescription>
    </Alert>
  );
}
