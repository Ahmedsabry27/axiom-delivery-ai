#!/usr/bin/env node
import { createRequire } from "node:module";
import { readFile, readdir } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(here, "../frontend/package.json"));
const { chromium } = require("playwright");
const requested = new Set(process.argv.slice(2));
const files = (await readdir(here))
  .filter((name) => name.startsWith("architecture_") && name.endsWith(".svg"))
  .filter((name) => requested.size === 0 || requested.has(path.basename(name, ".svg")))
  .sort();

const browser = await chromium.launch({ headless: true });
try {
  for (const file of files) {
    const source = await readFile(path.join(here, file), "utf8");
    const match = source.match(/<svg[^>]*width="(\d+)"[^>]*height="(\d+)"/);
    if (!match) throw new Error(`Missing SVG dimensions: ${file}`);
    const width = Number(match[1]);
    const height = Number(match[2]);
    const page = await browser.newPage({ viewport: { width, height } });
    await page.goto(pathToFileURL(path.join(here, file)).href, { waitUntil: "load" });
    await page.screenshot({ path: path.join(here, file.replace(/\.svg$/, ".png")) });
    await page.close();
    process.stdout.write(`${file}: ${width}x${height}\n`);
  }
} finally {
  await browser.close();
}
