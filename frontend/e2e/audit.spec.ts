import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
test("real API audit, decision verification, provenance and responsive layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Une histoire vérifiable." }),
  ).toBeVisible();
  await expect(
    page.getByText("Processus indépendants · même machine"),
  ).toBeVisible();
  await expect(page.getByText("Aucune expérience lancée")).toHaveCount(0);
  await page.getByRole("button", { name: "Explorer la provenance" }).click();
  await expect(
    page.getByText("Modèle · round 0", { exact: true }),
  ).toBeVisible();
  await page.getByText("Authentification locale des actions").click();
  const root = path.resolve("..");
  const python =
    process.env.FEDTRACE_PYTHON ||
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts" : "bin",
      process.platform === "win32" ? "python.exe" : "python",
    );
  const token = execFileSync(python, ["-m", "fedtrace.cli", "token"], {
    cwd: root,
    encoding: "utf8",
  }).trim();
  await page.getByLabel("Jeton du dépositaire local").fill(token);
  await page.getByRole("button", { name: "Simulation", exact: true }).click();
  await page.getByRole("button", { name: "Exécuter la simulation" }).click();
  await expect(
    page.getByText("Probabilité synthétique :", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Vérifier l’explication" }).click();
  await expect(page.getByText("Intégrité : Confirmé")).toBeVisible();
  await page
    .getByRole("button", { name: "Reconstituer la provenance" })
    .click();
  await expect(
    page.getByText("Décision synthétique", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Vue d’ensemble", exact: true })
    .click();
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: "../reports/dashboard-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../reports/dashboard-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
