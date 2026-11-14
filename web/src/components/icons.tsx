/* A small drawn icon set: 16px grid, 1.6 stroke, square caps, matching the ledger's ruled lines. */
import type { SVGProps } from "react";

function Icon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="square"
      aria-hidden="true"
      focusable="false"
      {...props}
    />
  );
}

export const BalancedIcon = () => (
  <Icon>
    <path d="M3 8.5l3 3 7-7" />
  </Icon>
);

export const BrokenIcon = () => (
  <Icon>
    <path d="M4 4l8 8M12 4l-8 8" />
  </Icon>
);

export const CopyIcon = () => (
  <Icon>
    <path d="M5.5 5.5h7v7h-7z" />
    <path d="M3.5 10.5v-7h7" />
  </Icon>
);

export const ResetIcon = () => (
  <Icon>
    <path d="M3 8a5 5 0 1 0 1.5-3.5" />
    <path d="M3 2.5V5h2.5" />
  </Icon>
);
