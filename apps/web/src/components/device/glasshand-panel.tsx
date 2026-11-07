import { ExternalLink } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { rentalReady, type GlasshandStatus } from "@/lib/glasshand";
import { GlasshandLive } from "./glasshand-live";

interface Props { status: GlasshandStatus; busy: boolean; onSelect: (id: string) => void; onDisconnect: () => void }

export function GlasshandPanel({ status, busy, onSelect, onDisconnect }: Props) {
  const rentals = status.rentals ?? [];
  const selected = rentals.find((r) => r.id === status.selected_rental_id);
  return (
    <section className="flex flex-col gap-3">
      {rentals.length === 0 && (
        <p className="text-xs text-muted-foreground">
          No active rental. Rent an iPhone at{" "}
          <a className="inline-flex items-center gap-0.5 underline" href="https://glasshand.com" target="_blank" rel="noopener noreferrer">glasshand.com<ExternalLink className="size-3" aria-hidden /></a>
        </p>
      )}
      {rentals.length > 1 && (
        <Select value={status.selected_rental_id ?? undefined} onValueChange={onSelect} disabled={busy}>
          <SelectTrigger aria-label="Rental" className="w-full"><SelectValue placeholder="Choose a rental" /></SelectTrigger>
          <SelectContent>
            {rentals.map((r) => (
              <SelectItem key={r.id} value={r.id} disabled={!rentalReady(r)}>{r.name}{rentalReady(r) ? "" : ` (${r.status})`}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
      {selected && rentalReady(selected) && <GlasshandLive rentalId={selected.id} />}
      <div className="flex flex-wrap justify-center gap-2">
        <Button size="sm" variant="outline" asChild>
          <a href="https://app.glasshand.com" target="_blank" rel="noopener noreferrer">Take control in Glasshand<ExternalLink aria-hidden /></a>
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild><Button size="sm" variant="ghost" disabled={busy}>Disconnect</Button></AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Disconnect Glasshand?</AlertDialogTitle>
              <AlertDialogDescription>Stored access tokens are deleted. You will need to approve a new email code to reconnect. Your rental is not cancelled.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep connected</AlertDialogCancel>
              <AlertDialogAction onClick={onDisconnect}>Disconnect</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </section>
  );
}
