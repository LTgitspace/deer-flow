"use client";

import { ShieldIcon } from "lucide-react";
import { useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useThreadNudges } from "@/core/threads/nudges";
import { cn } from "@/lib/utils";

interface GateActivityBadgeProps {
  threadId: string | undefined;
  className?: string;
}

export function GateActivityBadge({ threadId, className }: GateActivityBadgeProps) {
  const [open, setOpen] = useState(false);
  const { data: nudges, isLoading } = useThreadNudges(threadId, {
    enabled: open && !!threadId,
  });

  const hasNudges = (nudges?.length ?? 0) > 0;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          role="status"
          aria-label="Gate activity"
          title="Gate activity — recent deterministic enforcement"
          className={cn(
            "text-muted-foreground bg-background/70 flex size-7 items-center justify-center rounded-full border hover:text-foreground transition-colors",
            className,
          )}
        >
          <ShieldIcon size={14} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96 max-w-[90vw]">
        <DropdownMenuLabel>Gate activity</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {isLoading && open ? (
          <div className="text-muted-foreground px-3 py-2 text-xs">Loading...</div>
        ) : !hasNudges ? (
          <div className="text-muted-foreground px-3 py-2 text-xs">
            No gate triggers yet in this thread.
          </div>
        ) : (
          <div className="max-h-80 overflow-y-auto">
            {[...(nudges ?? [])].reverse().map((nudge, index) => (
              <div key={`${nudge.ts}-${index}`} className="px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{nudge.middleware}</span>
                  <span className="text-muted-foreground shrink-0">
                    {new Date(nudge.ts * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-muted-foreground mt-1 line-clamp-3">{nudge.text}</p>
              </div>
            ))}
          </div>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
