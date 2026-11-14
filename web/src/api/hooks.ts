import { useQuery } from "@tanstack/react-query";
import { useSession } from "./session";
import type {
  DiffOut,
  EventPage,
  RecordContentOut,
  RecordPage,
  StatsOut,
  VersionList,
} from "./types";

/** Query keys start with the tenant, so a reset or role switch never shows stale rows. */
function useScope() {
  const { session, call } = useSession();
  return { tenant: session?.tenant_id ?? null, role: session?.role ?? null, call };
}

export function useStats() {
  const { tenant, call } = useScope();
  return useQuery({
    queryKey: [tenant, "stats"],
    queryFn: () => call<StatsOut>("/stats"),
    enabled: tenant !== null,
  });
}

export function useRecords() {
  const { tenant, call } = useScope();
  return useQuery({
    queryKey: [tenant, "records"],
    queryFn: () => call<RecordPage>("/records?limit=100"),
    enabled: tenant !== null,
  });
}

export function useVersions(recordId: string | null) {
  const { tenant, call } = useScope();
  return useQuery({
    queryKey: [tenant, "versions", recordId],
    queryFn: () => call<VersionList>(`/records/${recordId}/versions`),
    enabled: tenant !== null && recordId !== null,
  });
}

export function useRecordVersion(recordId: string | null, versionNo: number | null) {
  const { tenant, role, call } = useScope();
  return useQuery({
    queryKey: [tenant, "content", recordId, versionNo],
    queryFn: () => call<RecordContentOut>(`/records/${recordId}/versions/${versionNo}`),
    enabled: tenant !== null && recordId !== null && versionNo !== null && role !== "auditor",
    retry: false,
  });
}

export function useDiff(recordId: string | null, from: number | null, to: number | null) {
  const { tenant, role, call } = useScope();
  return useQuery({
    queryKey: [tenant, "diff", recordId, from, to],
    queryFn: () => call<DiffOut>(`/records/${recordId}/diff?from=${from}&to=${to}`),
    enabled:
      tenant !== null &&
      recordId !== null &&
      from !== null &&
      to !== null &&
      from !== to &&
      role !== "auditor",
    retry: false,
  });
}

/** Newest entries, or the window around `focusSeq` (the entry that failed to reconcile). */
export function useEvents(focusSeq: number | null = null) {
  const { tenant, call } = useScope();
  const path = focusSeq === null ? "/events?limit=40" : `/events?limit=16&before_seq=${focusSeq + 9}`;
  return useQuery({
    queryKey: [tenant, "events", focusSeq],
    queryFn: () => call<EventPage>(path),
    enabled: tenant !== null,
  });
}
