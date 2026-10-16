import { expect, test, Page } from "@playwright/test";

const legacyWorkspace = "flowpilot_workspace_v1";
const legacyInventory = "flowpilot_inventory_editor_v1";
const currentWorkspace = "flowpilot_publication_workspace_v1";
const currentInventory = "flowpilot_publication_inventory_editor_v1";
const sentinel = "legacy-state-sentinel";

async function navigate(page: Page, mobile: boolean, name: string) {
  if (mobile) await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("button", { name, exact: true }).click();
}

async function seedDrafts(page: Page, includeCurrent: boolean) {
  await page.addInitScript(({ includeCurrent, sentinel, keys }) => {
    const workspace = JSON.stringify({ protocol: sentinel,
      intakePackage: { raw_protocol: sentinel, historical_data: sentinel },
      selectedProfile: { name: sentinel, profile_id: sentinel, lab_inventory: {} } });
    const inventory = JSON.stringify({ draft: { name: sentinel, profile_id: sentinel, lab_inventory: {} }, jsonText: sentinel });
    sessionStorage.setItem(keys[0], workspace);
    sessionStorage.setItem(keys[1], inventory);
    if (includeCurrent) {
      sessionStorage.setItem(keys[2], workspace);
      sessionStorage.setItem(keys[3], inventory);
    }
  }, { includeCurrent, sentinel, keys: [legacyWorkspace, legacyInventory, currentWorkspace, currentInventory] });
}

test("fresh normal workspace ignores legacy browser drafts without deleting them", async ({ page }, info) => {
  await seedDrafts(page, false);
  await page.goto("/");
  await expect(page.getByLabel("Initial batch protocol")).toHaveValue("");
  await expect(page.locator(".resultWorkspace")).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText(sentinel);
  await expect(page.locator("body")).not.toContainText("Synthetic interface example");

  await navigate(page, info.project.name === "mobile", "Inventory");
  await expect(page.getByLabel("Profile name", { exact: true })).not.toHaveValue(sentinel);
  await expect(page.locator("body")).not.toContainText(sentinel);
  await navigate(page, info.project.name === "mobile", "Saved runs");
  await expect(page.getByText("No autosaved runs", { exact: true })).toBeVisible();
  expect((await (await page.request.get("/api/runs")).json()).runs).toEqual([]);
  expect((await (await page.request.get("/api/inventory/profiles")).json()).profiles).toEqual([]);
  const legacy = await page.evaluate(keys => keys.map(key => sessionStorage.getItem(key)), [legacyWorkspace, legacyInventory]);
  expect(legacy.every(value => value?.includes(sentinel))).toBe(true);
});

test("fictional demo never reads backend state, restores drafts, or overwrites drafts", async ({ page }, info) => {
  await seedDrafts(page, true);
  const apiRequests: string[] = [];
  page.on("request", request => { if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url()); });
  await page.goto("/?demo=1&run=legacy-state-sentinel&job=legacy-state-sentinel");
  const savedBefore = await page.evaluate(keys => keys.map(key => sessionStorage.getItem(key)), [legacyWorkspace, legacyInventory, currentWorkspace, currentInventory]);
  await expect(page.getByText("Synthetic interface example", { exact: true })).toBeVisible();
  await expect(page.getByText("10 min", { exact: true })).toBeVisible();
  await expect(page.locator("body")).not.toContainText(sentinel);
  await page.getByRole("button", { name: "Council", exact: true }).click();
  await expect(page.getByText("No council run", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Experiment loop", exact: true }).click();
  await expect(page.getByText("No experimental outcomes", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await navigate(page, info.project.name === "mobile", "Inventory");
  await expect(page.getByText("No inventory in this preview", { exact: true })).toBeVisible();
  await navigate(page, info.project.name === "mobile", "Saved runs");
  await expect(page.getByText("No autosaved runs", { exact: true })).toBeVisible();
  await navigate(page, info.project.name === "mobile", "Status");
  await expect(page.getByText("Offline interface preview", { exact: true })).toBeVisible();
  expect(apiRequests).toEqual([]);
  const savedAfter = await page.evaluate(keys => keys.map(key => sessionStorage.getItem(key)), [legacyWorkspace, legacyInventory, currentWorkspace, currentInventory]);
  expect(savedAfter).toEqual(savedBefore);
});
