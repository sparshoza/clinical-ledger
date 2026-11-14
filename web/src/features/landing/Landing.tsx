import type { ReactNode } from "react";
import {
  ARCHITECTURE_URL,
  BENCHMARKS_URL,
  DEMO_PATH,
  PORTFOLIO_URL,
  REPO_URL,
} from "../../lib/links";

/** The mechanisms, in the order a visitor meets them in the demo. */
const MECHANISMS: { term: string; detail: string }[] = [
  {
    term: "Nothing is overwritten",
    detail:
      "A change to a record inserts a new version and moves the record's head pointer. The database itself rejects updates and deletes on versions, files and the journal, and the app's login cannot switch that off.",
  },
  {
    term: "Every action is chained",
    detail:
      "Each journal entry stores a SHA-256 hash of its own fields plus the previous entry's hash. Edit any entry and every link after it stops adding up, and verification names the first one that fails.",
  },
  {
    term: "Files are addressed by their hash",
    detail:
      "Documents are stored in S3-compatible storage under their own SHA-256. Every read rehashes the bytes, so a file altered in storage is refused instead of shown.",
  },
  {
    term: "Any point in time",
    detail:
      "The latest version is one indexed lookup however long the history grows. Any record can be read as it stood at a past moment, and any two versions compared line by line.",
  },
  {
    term: "Isolated by the database",
    detail:
      "Each visitor gets a private tenant. PostgreSQL row-level security scopes every query to it, so a missing filter in application code still cannot reach another visitor's rows.",
  },
  {
    term: "Reads are logged too",
    detail:
      "Clinicians read and write, auditors see the journal but not content, admins can tamper. Every read of record content is itself a journal entry.",
  },
];

const MEASURED: { operation: string; p50: string; p95: string }[] = [
  { operation: "Add a version", p50: "1.36 ms", p95: "2.47 ms" },
  { operation: "Read the latest of 10,000 versions", p50: "0.86 ms", p95: "1.64 ms" },
  { operation: "Read as of a past time", p50: "1.21 ms", p95: "2.48 ms" },
];

const STACK = ["Python 3.12 and FastAPI", "PostgreSQL 16 (Neon)", "Cloudflare R2", "React and TypeScript", "Vercel"];

type Props = {
  /** The live ledger panel; a slot so the page renders without the API in tests. */
  preview: ReactNode;
};

/** What Clinical Ledger is and does, with a way into the demo and the code. */
export function Landing({ preview }: Props) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-[76rem] flex-col px-4 sm:px-6">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-2 py-4">
        <a href="/" className="text-ink text-lg font-semibold tracking-tight no-underline">
          Clinical Ledger
        </a>
        <nav aria-label="Site" className="flex sm:ml-auto flex-wrap gap-x-5 gap-y-1 text-sm">
          <a href={DEMO_PATH}>Demo</a>
          <a href={REPO_URL}>Source on GitHub</a>
          <a href={BENCHMARKS_URL}>Benchmarks</a>
          <a href={PORTFOLIO_URL}>Sparsh Oza</a>
        </nav>
      </header>

      <main className="grid flex-1 gap-x-14 gap-y-10 pt-10 pb-16 lg:grid-cols-[minmax(0,1fr)_24rem] lg:grid-rows-[auto_1fr] lg:pt-16">
        {/* Phones read hero, then the live ledger, then the explanation; wide screens keep the
            ledger as a sticky column beside both. */}
        <div className="min-w-0 lg:col-start-1">
          <h1 className="max-w-[16ch] text-4xl leading-[1.08] font-semibold tracking-[-0.02em] [text-wrap:balance] sm:text-5xl">
            Clinical records that cannot be quietly rewritten.
          </h1>
          <p className="text-ink-2 mt-5 max-w-[60ch] text-lg leading-relaxed">
            Clinical Ledger keeps every version of every record and writes every action into a
            journal where each entry carries the hash of the one before it. Change a single byte,
            in the database or in file storage, and verification points to the exact entry that no
            longer adds up.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <a className="btn btn-primary btn-lg" href={DEMO_PATH}>
              Open the demo
            </a>
            <a className="btn btn-quiet btn-lg" href="#how">
              See how it works
            </a>
          </div>
          <p className="text-ink-2 mt-4 text-sm">
            All records are synthetic, generated with Synthea. No real patient data is used.
          </p>
        </div>

        <aside className="lg:sticky lg:top-6 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-start">
          {preview}
        </aside>

        <div className="min-w-0 lg:col-start-1">
          <section aria-labelledby="try" className="lg:mt-6">
            <h2 id="try" className="ledger-head pb-1 text-lg font-semibold">
              Try it in a minute
            </h2>
            <p className="mt-3 max-w-[64ch] leading-relaxed">
              Open a patient&apos;s record and step through its versions with the as-of slider.
              Press <strong className="font-semibold">Tamper with the log</strong>, which quietly
              edits one journal entry behind the app&apos;s back, then{" "}
              <strong className="font-semibold">Verify the chain</strong>: the entry that no longer
              reconciles is struck through, with its stored and recomputed hash side by side.
              Switch to the auditor role to see the journal without the content, and reset whenever
              you like.
            </p>
          </section>

          <section aria-labelledby="how" className="mt-14">
            <h2 id="how" className="ledger-head scroll-mt-6 pb-1 text-lg font-semibold">
              How it works
            </h2>
            <dl className="mt-1">
              {MECHANISMS.map(({ term, detail }) => (
                <div
                  key={term}
                  className="ledger-rule grid gap-x-8 gap-y-1 py-4 sm:grid-cols-[13rem_minmax(0,1fr)]"
                >
                  <dt className="font-semibold">{term}</dt>
                  <dd className="text-ink-2 max-w-[62ch] leading-relaxed">{detail}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-4 text-sm">
              <a href={ARCHITECTURE_URL}>Read the architecture notes and design decisions</a>
            </p>
          </section>

          <section aria-labelledby="measured" className="mt-14">
            <h2 id="measured" className="ledger-head pb-1 text-lg font-semibold">
              Measured, not claimed
            </h2>
            <p className="text-ink-2 mt-3 max-w-[64ch] leading-relaxed">
              One tenant holding two million journal entries over half a million versions, on
              PostgreSQL 16 running on a laptop. Read time stays flat as a record&apos;s history
              grows.
            </p>
            <table aria-label="Measured on a laptop" className="mt-4 w-full max-w-xl border-collapse text-sm">
              <thead>
                <tr className="ledger-head text-ink-2 text-left text-xs">
                  <th scope="col" className="py-1 pr-4 font-medium">Operation</th>
                  <th scope="col" className="py-1 pr-4 text-right font-medium">Median</th>
                  <th scope="col" className="py-1 text-right font-medium">95th percentile</th>
                </tr>
              </thead>
              <tbody>
                {MEASURED.map((row) => (
                  <tr key={row.operation} className="ledger-rule">
                    <td className="py-1.5 pr-4">{row.operation}</td>
                    <td className="py-1.5 pr-4 text-right font-semibold">{row.p50}</td>
                    <td className="py-1.5 text-right">{row.p95}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-sm">
              <a href={BENCHMARKS_URL}>Method and hardware, and how to reproduce every number</a>
            </p>
          </section>

          <section aria-labelledby="stack" className="mt-14">
            <h2 id="stack" className="ledger-head pb-1 text-lg font-semibold">
              Built with
            </h2>
            <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
              {STACK.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>
        </div>
      </main>

      <footer className="border-rule text-ink-2 flex flex-wrap gap-x-5 gap-y-1 border-t py-5 text-sm">
        <span>Built by Sparsh Oza. Synthetic data from Synthea; this is a demonstration, not a certified medical system.</span>
        <a href="/api/docs">API reference</a>
      </footer>
    </div>
  );
}
