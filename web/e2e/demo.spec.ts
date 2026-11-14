import { expect, test } from "@playwright/test";

test("tampering is caught and a reset balances the book again", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Clinical Ledger" })).toBeVisible();
  await expect(page.getByText(/synthetic \(Synthea\)/)).toBeVisible();
  await expect(page.getByText(/350 entries/)).toBeVisible({ timeout: 20_000 });

  await expect(page.getByRole("radio", { name: "Admin" })).toBeChecked();
  await page.getByRole("button", { name: "Tamper with the log" }).click();
  await expect(page.getByText(/Run Verify the chain/)).toBeVisible();

  await page.getByRole("button", { name: "Verify the chain" }).click();
  await expect(page.getByText(/Broken at entry #/)).toBeVisible();
  await expect(page.getByText("Does not reconcile").first()).toBeVisible();

  await page.getByRole("button", { name: "Reset the demo" }).click();
  await page.getByRole("button", { name: "Verify the chain" }).click();
  await expect(page.getByText(/Chain intact/)).toBeVisible();
});

test("an auditor sees the journal but not record content", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/350 entries/)).toBeVisible({ timeout: 20_000 });
  await page.getByRole("radio", { name: "Auditor" }).click({ force: true });
  await expect(page.getByText("Auditors can see the log but not record content.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Journal" })).toBeVisible();
});
