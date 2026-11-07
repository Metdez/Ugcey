import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

/** Single-select filter chips; clicking the active chip keeps it selected. */
export function Chips<T extends string>({ value, onChange, options, label }: {
  value: T; onChange: (v: T) => void; options: readonly { value: T; label: string }[]; label: string;
}) {
  return (
    <ToggleGroup type="single" variant="outline" size="sm" value={value} aria-label={label} className="flex-wrap"
      onValueChange={(v) => v && onChange(v as T)}>
      {options.map((o) => <ToggleGroupItem key={o.value} value={o.value} className="px-2.5 text-xs">{o.label}</ToggleGroupItem>)}
    </ToggleGroup>
  );
}
