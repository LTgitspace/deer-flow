"use client";

import { useQuery } from "@tanstack/react-query";

export interface NudgeEntry {
  thread_id: string;
  middleware: string;
  text: string;
  level: string;
  ts: number;
}

export interface NudgesResponse {
  thread_id: string;
  nudges: NudgeEntry[];
}

async function fetchNudges(threadId: string, apiUrl: string): Promise<NudgeEntry[]> {
  const response = await fetch(
    `${apiUrl}/api/console/threads/${encodeURIComponent(threadId)}/nudges?limit=50`,
    { credentials: "include" },
  );
  if (!response.ok) {
    throw new Error(`Failed to load nudges: ${response.status}`);
  }
  const data = (await response.json()) as NudgesResponse;
  return data.nudges ?? [];
}

export function useThreadNudges(threadId: string | undefined, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: ["thread-nudges", threadId],
    queryFn: () => fetchNudges(threadId ?? "", window.location.origin),
    enabled: enabled && !!threadId,
    refetchInterval: 5000,
    refetchOnWindowFocus: false,
  });
}
