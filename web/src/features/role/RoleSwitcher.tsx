import type { Role } from "../../api/types";

const ROLES: { value: Role; label: string }[] = [
  { value: "clinician", label: "Clinician" },
  { value: "auditor", label: "Auditor" },
  { value: "admin", label: "Admin" },
];

/** Sign in as another demo role. The visitor keeps the same private ledger. */
export function RoleSwitcher({
  role,
  onChange,
  busy,
}: {
  role: Role;
  onChange: (role: Role) => void;
  busy: boolean;
}) {
  return (
    <fieldset className="flex items-center gap-2 text-sm" disabled={busy}>
      <legend className="sr-only">Signed in as</legend>
      <span className="text-ink-2" aria-hidden="true">
        Signed in as
      </span>
      <div className="flex rounded-[4px] shadow-[inset_0_0_0_1px_var(--color-rule-strong)]">
        {ROLES.map((option) => (
          <label
            key={option.value}
            className={`cursor-pointer px-2.5 py-1 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-action ${
              option.value === role ? "bg-action text-action-ink font-semibold" : "text-ink"
            } first:rounded-l-[4px] last:rounded-r-[4px]`}
          >
            <input
              type="radio"
              name="role"
              value={option.value}
              checked={option.value === role}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
