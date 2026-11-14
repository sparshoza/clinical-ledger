/** "9f3c…a1": enough to recognise a hash at a glance; the full value is a click away. */
export function shortHash(hash: string): string {
  return hash.length <= 8 ? hash : `${hash.slice(0, 4)}…${hash.slice(-2)}`;
}

export function formatRelative(iso: string, now: Date = new Date()): string {
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}

const DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}

export function formatTime(iso: string): string {
  return TIME.format(new Date(iso));
}

/** "Patient/068177c1-…" becomes "Patient 068177c1". */
export function patientLabel(subjectRef: string): string {
  const match = /^Patient\/([0-9a-f]{8})/.exec(subjectRef);
  return match ? `Patient ${match[1]}` : subjectRef;
}

const KINDS: Record<string, string> = {
  "patient-summary": "Patient summary",
  "imaging-report": "Imaging report",
  "lab-panel": "Lab panel",
};

export function kindLabel(kind: string): string {
  return KINDS[kind] ?? kind;
}

const EVENTS: Record<string, string> = {
  "record.created": "Record created",
  "version.added": "Version added",
  "record.read": "Record read",
  "version.read": "Version read",
  "verify.run": "Verification run",
};

export function eventLabel(eventType: string): string {
  return EVENTS[eventType] ?? eventType;
}
