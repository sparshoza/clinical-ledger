import type { Problem } from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.title);
    this.status = problem.status;
    this.problem = problem;
  }

  get slug(): string {
    return this.problem.type?.split("/").at(-1) ?? "";
  }
}

type Options = { token?: string | null; method?: string; body?: unknown };

/** Fetch a JSON endpoint under /api/v1. Errors become ApiError carrying the problem body. */
export async function apiFetch<T>(path: string, { token, method = "GET", body }: Options = {}) {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError({ status: 503, title: "The server could not be reached" });
  }
  if (!response.ok) {
    let problem: Problem = { status: response.status, title: response.statusText || "Request failed" };
    try {
      problem = { ...problem, ...((await response.json()) as Problem) };
    } catch {
      /* not JSON: keep the status line */
    }
    throw new ApiError(problem);
  }
  return (await response.json()) as T;
}
