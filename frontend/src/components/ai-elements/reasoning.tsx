"use client";

import { useControllableState } from "@radix-ui/react-use-controllable-state";
import {
  Collapsible,
  type CollapsibleContent,
  type CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { BrainIcon } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { createContext, memo, useContext, useEffect, useState } from "react";
import { reasoningPlugins } from "@/core/streamdown/plugins";
import { Shimmer } from "./shimmer";
import { ClipboardSafeStreamdown } from "./streamdown";

type ReasoningContextValue = {
  isStreaming: boolean;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  duration: number | undefined;
  startTime: number | null;
};

const ReasoningContext = createContext<ReasoningContextValue | null>(null);

export const useReasoning = () => {
  const context = useContext(ReasoningContext);
  if (!context) {
    throw new Error("Reasoning components must be used within Reasoning");
  }
  return context;
};

type ReasoningProps = ComponentProps<typeof Collapsible> & {
  isStreaming?: boolean;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  duration?: number;
  startTimeProp?: number | null;
  onTurnDurationChange?: (duration: number | undefined) => void;
};

const MS_IN_S = 1000;

export const Reasoning = memo(
  ({
    className,
    isStreaming = false,
    open,
    defaultOpen = true,
    onOpenChange,
    duration: durationProp,
    startTimeProp,
    onTurnDurationChange,
    children,
    ...props
  }: ReasoningProps) => {
    const [isOpen, setIsOpen] = useControllableState({
      prop: open,
      defaultProp: defaultOpen,
      onChange: onOpenChange,
    });
    const [duration, setDuration] = useControllableState<number | undefined>({
      prop: durationProp,
      defaultProp: undefined,
      onChange: onTurnDurationChange,
    });

    const [startTime, setStartTime] = useState<number | null>(
      () => startTimeProp ?? (isStreaming ? Date.now() : null),
    );

    // Track duration when streaming starts and ends
    useEffect(() => {
      if (isStreaming) {
        // Force sync the start time with the Turn start time if provided
        if (startTimeProp != null && startTime !== startTimeProp) {
          setStartTime(startTimeProp);
        } else if (startTimeProp == null && startTime === null) {
          setStartTime(Date.now());
        }
      } else if (startTime !== null) {
        setDuration(Math.floor((Date.now() - startTime) / MS_IN_S));
        setStartTime(null);
      }
    }, [isStreaming, startTimeProp, startTime, setDuration]);

    // Always visible: no auto-close. Reasoning stays open after streaming ends.

    const handleOpenChange = (newOpen: boolean) => {
      setIsOpen(newOpen);
    };

    return (
      <ReasoningContext.Provider
        value={{ isStreaming, isOpen, setIsOpen, duration, startTime }}
      >
        <Collapsible
          className={cn("not-prose mb-4", className)}
          onOpenChange={handleOpenChange}
          open={isOpen}
          {...props}
        >
          {children}
        </Collapsible>
      </ReasoningContext.Provider>
    );
  },
);

export type ReasoningTriggerProps = {
  className?: string;
  children?: ReactNode;
  getThinkingMessage?: (
    isStreaming: boolean,
    duration?: number,
    startTime?: number | null,
  ) => ReactNode;
  hasContent?: boolean;
};

const LiveTimer = ({ startTime }: { startTime: number }) => {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const calculateElapsed = () => Math.floor((Date.now() - startTime) / 1000);
    setElapsed(calculateElapsed());

    const interval = setInterval(() => {
      setElapsed(calculateElapsed());
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  return (
    <span className="flex items-center gap-2">
      <Shimmer duration={1}>Thinking...</Shimmer>
      <span className="text-muted-foreground/80">({elapsed}s)</span>
    </span>
  );
};

const defaultGetThinkingMessage = (
  isStreaming: boolean,
  duration?: number,
  startTime?: number | null,
) => {
  if (isStreaming && startTime != null && startTime !== undefined) {
    return <LiveTimer startTime={startTime} />;
  }
  if (isStreaming || duration === 0) {
    return <Shimmer duration={1}>Thinking...</Shimmer>;
  }
  if (duration === undefined) {
    return <span>Thinking</span>;
  }
  return <span>Thinking ({duration}s)</span>;
};

export const ReasoningTrigger = memo(
  ({
    className,
    children,
    getThinkingMessage = defaultGetThinkingMessage,
    hasContent = true,
    ...props
  }: ReasoningTriggerProps) => {
    const { isStreaming, duration, startTime } = useReasoning();

    return (
      <div
        className={cn(
          "text-muted-foreground flex w-full items-center gap-2 text-sm",
          className,
        )}
        {...props}
      >
        {children ?? (
          <>
            <BrainIcon className="size-4 opacity-70" />
            {getThinkingMessage(isStreaming, duration, startTime)}
          </>
        )}
      </div>
    );
  },
);

export type ReasoningContentProps = ComponentProps<
  typeof CollapsibleContent
> & {
  children: string;
};

export const ReasoningContent = memo(
  ({ className, children, ...props }: ReasoningContentProps) => (
    <div
      className={cn(
        "mt-2 text-sm text-muted-foreground/90",
        className,
      )}
      {...props}
    >
      <ClipboardSafeStreamdown {...reasoningPlugins}>
        {children}
      </ClipboardSafeStreamdown>
    </div>
  ),
);

Reasoning.displayName = "Reasoning";
ReasoningTrigger.displayName = "ReasoningTrigger";
ReasoningContent.displayName = "ReasoningContent";
