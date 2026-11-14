export type Route = "landing" | "demo";

/** The console lives at /demo; every other path shows the landing page. */
export function routeFor(pathname: string): Route {
  return /^\/demo(\/|$)/.test(pathname) ? "demo" : "landing";
}
