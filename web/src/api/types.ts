import type { components } from "./schema";

type Schemas = components["schemas"];

export type Role = Schemas["DemoSignIn"]["role"];
export type SessionOut = Schemas["SessionOut"];
export type StatsOut = Schemas["StatsOut"];
export type RecordSummaryOut = Schemas["RecordSummaryOut"];
export type RecordPage = Schemas["RecordPage"];
export type RecordContentOut = Schemas["RecordContentOut"];
export type VersionOut = Schemas["VersionOut"];
export type VersionList = Schemas["VersionList"];
export type DiffOut = Schemas["DiffOut"];
export type EventOut = Schemas["EventOut"];
export type EventPage = Schemas["EventPage"];
export type VerifyOut = Schemas["VerifyOut"];
export type TamperOut = Schemas["TamperOut"];

/** RFC 9457 problem body returned by every API error. */
export type Problem = { type?: string; title: string; status: number; detail?: string };
