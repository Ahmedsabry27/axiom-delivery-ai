import {expect,test} from "@playwright/test";

test("release readiness and notes remain interactive without console errors",async({page})=>{
  const consoleErrors:string[]=[];
  page.on("console",message=>{if(message.type()==="error")consoleErrors.push(message.text());});

  await page.goto("/releases");
  await expect(page.getByRole("heading",{name:"Releases"})).toBeVisible();
  await expect(page.getByText("AX Platform 1.0",{exact:true})).toBeVisible();
  await page.goto("/releases/rel-001");
  await expect(page.getByRole("heading",{name:"AX Platform 1.0"})).toBeVisible();

  await page.getByRole("link",{name:"Readiness"}).click();
  await expect(page).toHaveURL(/\/releases\/rel-001\/readiness$/);
  await expect(page.getByText("20 / 22 evidence items verified")).toBeVisible();
  await expect(page.getByText("CONDITIONAL GO").first()).toBeVisible();

  await page.getByRole("button",{name:"Record Decision"}).first().click();
  const dialog=page.getByRole("dialog",{name:"Record release decision"});
  await dialog.getByLabel("Conditions").fill("Security approval before deployment");
  await dialog.getByRole("button",{name:"Continue"}).click();
  await expect(dialog.getByText("Confirm release decision")).toBeVisible();
  await dialog.getByRole("button",{name:"Confirm decision"}).click();
  await expect(page.getByRole("status")).toContainText("Decision recorded successfully");

  await page.getByRole("link",{name:"Release Notes"}).click();
  await expect(page).toHaveURL(/\/releases\/rel-001\/release-notes$/);
  await expect(page.getByRole("heading",{name:"Release Notes"})).toBeVisible();
  await expect(page.getByText(/Jira/i).first()).toBeVisible();
  expect(consoleErrors).toEqual([]);
});
