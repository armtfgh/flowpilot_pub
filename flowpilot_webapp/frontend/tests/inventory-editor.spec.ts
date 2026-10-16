import { expect, test, Page } from "@playwright/test";
import fs from "node:fs/promises";

async function openInventory(page: Page, mobile: boolean) {
  page.on("dialog", dialog => dialog.accept());
  await page.goto("/");
  if (mobile) await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await expect(page.getByLabel("Profile name", { exact: true })).toBeVisible();
}

async function uploadExample(page: Page) {
  const response = await page.request.post("/api/inventory/import", { data: {
    name: "Example laboratory", profile_id: "example_browser_inventory",
    lab_inventory: { pumps: [{ name: "Example pump", type: "syringe", quantity: 2,
      min_flow_rate_mL_min: 0.01, max_flow_rate_mL_min: 10, max_pressure_bar: 10,
      compatible_systems: ["example_coil"], notes: "Synthetic browser fixture." }],
      reactors: [{name: "Example coil", type: "coil", volume_mL: 10, material: "PFA", ID_mm: 1}],
      tubing: [], light_sources: [] },
    provenance: [{source_id: "fixture", filename: "example.json", sha256: "0".repeat(64)}],
    operating_constraints: {inline_degasser_available: false}
  } });
  expect(response.ok()).toBe(true);
  const profile = await response.json();
  await page.getByLabel("Import inventory JSON").setInputFiles({ name: "example.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(profile)) });
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeEnabled();
  return profile;
}

test("manual fields create a compatible profile and gate stale edits", async ({ page }, info) => {
  await openInventory(page, info.project.name === "mobile");
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeDisabled();
  await page.getByLabel("Profile name", { exact: true }).fill("Structured form test");
  await page.getByRole("button", { name: "Add equipment", exact: true }).click();
  const form = page.getByRole("dialog");
  await form.getByLabel("Equipment name", { exact: true }).fill("Test pump");
  await form.getByLabel("Type", { exact: false }).fill("syringe");
  await form.getByLabel("Minimum flow (mL/min)").fill("0.01");
  await form.getByLabel("Maximum flow (mL/min)").fill("10");
  await form.getByLabel("Maximum pressure (bar)").fill("10");
  await form.getByLabel("Flow setting increment (mL/min)").fill("0.005");
  await form.getByRole("button", { name: "Apply equipment" }).click();
  await page.getByRole("navigation", { name: "Equipment categories" }).getByRole("button", { name: /^Reactors/ }).click();
  await page.getByRole("button", { name: "Add equipment", exact: true }).click();
  await form.getByLabel("Equipment name", { exact: true }).fill("Manual PFA coil");
  await form.getByLabel("Type", { exact: false }).fill("coil");
  await form.getByLabel("Material").fill("PFA");
  await form.getByLabel("Volume (mL)").fill("10");
  await form.getByLabel("Internal diameter (mm)").fill("1");
  await form.getByRole("button", { name: "Apply equipment" }).click();
  await page.getByRole("button", { name: "Constraints", exact: true }).click();
  await page.getByRole("combobox", { name: "Inline degasser", exact: true }).selectOption("unavailable");
  await page.getByLabel("Allowed degassing alternatives").fill("offline pre-degassing");
  await page.getByRole("button", { name: "Validate profile", exact: true }).click();
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeEnabled();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON", exact: true }).click();
  const data = JSON.parse(await fs.readFile(await (await download).path() as string, "utf8"));
  expect(data.lab_inventory.pumps[0].min_flow_rate_mL_min).toBe(0.01);
  expect(data.lab_inventory.pumps[0].flow_rate_increment_mL_min).toBe(0.005);
  expect(data.equipment_capabilities.inline_degassing.available).toBe(false);
  expect(data.validation.valid).toBe(true);
  await page.getByLabel("Profile name", { exact: true }).fill("Changed draft");
  await expect(page.getByRole("button", { name: "Use in design", exact: true })).toBeDisabled();
  await page.reload();
  if (info.project.name === "mobile") await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("button", { name: "Inventory", exact: true }).click();
  await expect(page.getByLabel("Profile name", { exact: true })).toHaveValue("Changed draft");
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeDisabled();
  await page.screenshot({ path: info.outputPath("manual-constraints.png"), fullPage: true });
});

test("Inventory edit and JSON roundtrip preserve compatibility and export exact draft", async ({ page }, info) => {
  await openInventory(page, info.project.name === "mobile");
  const original = await uploadExample(page);
  expect(await page.locator(".equipmentCategories button").count()).toBe(15);
  await page.getByRole("button", { name: `Edit ${original.lab_inventory.pumps[0].name}`, exact: true }).click();
  const form = page.getByRole("dialog");
  await form.getByLabel("Notes", { exact: true }).fill("Edited by browser test");
  await form.getByRole("button", { name: "Apply equipment" }).click();
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Validate profile", exact: true }).click();
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeEnabled();
  const wait = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON", exact: true }).click();
  const exported = JSON.parse(await fs.readFile(await (await wait).path() as string, "utf8"));
  const expected = structuredClone(original.lab_inventory); expected.pumps[0].notes = "Edited by browser test";
  expect(exported.lab_inventory).toEqual(expected);
  expect(exported.provenance).toEqual(original.provenance);
  expect(exported.operating_constraints).toEqual(original.operating_constraints);
  await page.getByRole("button", { name: "JSON", exact: true }).click();
  await page.getByLabel("Inventory profile JSON").fill("{ invalid");
  await page.getByRole("button", { name: "Validate profile", exact: true }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "Use in design", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Discard JSON edits" }).click();
  await page.getByRole("button", { name: "Equipment", exact: true }).click();
  await expect(page.locator(".equipmentRows")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
  await page.screenshot({ path: info.outputPath("example-equipment.png"), fullPage: true });
});

test("advanced constraints cannot be silently bypassed and bind to design", async ({ page }, info) => {
  await openInventory(page, info.project.name === "mobile");
  await uploadExample(page);
  await page.getByRole("button", { name: "Constraints", exact: true }).click();
  await page.getByText("Additional limits, capabilities and shared resources", { exact: true }).click();
  await page.getByLabel("Operating constraints (JSON)").fill('{"inline_degasser_available":false,"custom_test_limit":3}');
  await expect(page.getByRole("button", { name: "Export JSON", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Validate profile", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Apply the additional constraint edits");
  await page.getByRole("button", { name: "Apply operating constraints", exact: true }).click();
  await page.getByRole("button", { name: "Validate profile", exact: true }).click();
  await expect(page.getByRole("button", { name: "Use in design", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Use in design", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Design studio", exact: true })).toBeVisible();
  const stored = await page.evaluate(() => JSON.parse(sessionStorage.getItem("flowpilot_publication_workspace_v1") || "{}"));
  expect(JSON.stringify(stored)).toContain('custom_test_limit');
});
