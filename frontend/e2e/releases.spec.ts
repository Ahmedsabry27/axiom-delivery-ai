import {expect,test} from "@playwright/test";
import { mockReleases } from "../src/features/releases/data/mockReleases";
import { mockReleaseNotesMap } from "../src/features/releases/data/mockReleaseNotes";

test("release readiness and notes remain interactive without console errors",async({page})=>{
  const consoleErrors:string[]=[];
  page.on("console",message=>{if(message.type()==="error")consoleErrors.push(message.text());});
  const release = { ...mockReleases[0], releaseNotes: mockReleaseNotesMap["rel-001"] };
  await page.route("**/api/delivery/metadata", route => route.fulfill({ json: { portfolios: [], programmes: [], projects: [], teams: [] } }));
  await page.route("**/api/releases**", route => {
    const url = new URL(route.request().url());
    if (route.request().method() === "POST") return route.fulfill({ json: release });
    if (url.pathname === "/api/releases") return route.fulfill({ json: { items: [release] } });
    return route.fulfill({ json: release });
  });

  await page.goto("/releases");
  await expect(page.getByRole("heading",{name:"Releases"})).toBeVisible();
  await expect(page.getByText("AX Platform 1.0",{exact:true})).toBeVisible();
  await page.goto("/releases/rel-001");
  await expect(page.getByRole("heading",{name:"AX Platform 1.0"})).toBeVisible();

  await page.getByRole("link",{name:"Readiness"}).click();
  await expect(page).toHaveURL(/\/releases\/rel-001\/readiness$/);
  await expect(page.getByText("20 / 22 evidence items verified")).toBeVisible();
  await expect(page.getByText("CONDITIONAL GO").first()).toBeVisible();

  await expect(page.getByText("You do not have permission to record this release decision.")).toBeVisible();

  await page.getByRole("link",{name:"Release Notes"}).click();
  await expect(page).toHaveURL(/\/releases\/rel-001\/release-notes$/);
  await expect(page.getByRole("heading",{name:"Release Notes"})).toBeVisible();
  await expect(page.getByText(/Jira/i).first()).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
