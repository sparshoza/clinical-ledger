import { expect, test } from "@playwright/test";

test("tampering is caught and a reset balances the book again", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "Clinical Ledger" })).toBeVisible();
  await expect(page.getByText(/synthetic \(Synthea\)/)).toBeVisible();
  const about = page.getByRole("navigation", { name: "About this project" });
  await expect(about.getByRole("link", { name: "Source on GitHub" })).toBeVisible();
  await expect(page.getByText(/350 entries/)).toBeVisible({ timeout: 20_000 });

  await expect(page.getByRole("radio", { name: "Admin" })).toBeChecked();
  await page.getByRole("button", { name: "Tamper with the log" }).click();
  await expect(page.getByText(/Run Verify the chain/)).toBeVisible();

  await page.getByRole("button", { name: "Verify the chain" }).click();
  await expect(page.getByText(/Broken at entry #/)).toBeVisible();
  await expect(page.getByText("Does not reconcile").first()).toBeVisible();
  await expect(page.getByText(/Recomputed/)).toBeVisible();

  await page.getByRole("button", { name: "Reset the demo" }).click();
  await page.getByRole("button", { name: "Verify the chain" }).click();
  await expect(page.getByText(/Chain intact/)).toBeVisible();
});

test("an auditor sees the journal but not record content", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByText(/350 entries/)).toBeVisible({ timeout: 20_000 });
  await page.getByRole("radio", { name: "Auditor" }).click({ force: true });
  await expect(page.getByText("Auditors can see the log but not record content.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Journal" })).toBeVisible();
});

test("the landing page explains the project and leads into the demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/entries/).first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Verify the chain" }).click();
  await expect(page.getByText(/Chain intact/)).toBeVisible();
  await page.getByRole("link", { name: "Open the demo" }).first().click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("table", { name: "Journal" })).toBeVisible({ timeout: 20_000 });
});
