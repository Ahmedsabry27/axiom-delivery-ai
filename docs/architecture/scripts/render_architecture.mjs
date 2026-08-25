#!/usr/bin/env node
import { createRequire } from "node:module";
import { mkdir, readFile, readdir } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, "..");
const svgDir = path.join(base, "svg");
const pngDir = path.join(base, "png");
const require = createRequire(path.resolve(base, "../../frontend/package.json"));
const { chromium } = require("playwright");
await mkdir(pngDir, { recursive: true });
const files = (await readdir(svgDir)).filter((x) => x.endsWith(".svg")).sort();
const browser = await chromium.launch({ headless: true });
try {
  for (const file of files) {
    const source = await readFile(path.join(svgDir, file), "utf8");
    const size = source.match(/<svg[^>]*width="(\d+)"[^>]*height="(\d+)"/);
    if (!size) throw new Error(`Missing SVG size: ${file}`);
    const [width, height] = size.slice(1).map(Number);
    const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(path.join(svgDir, file)).href, { waitUntil: "load" });
    await page.screenshot({ path: path.join(pngDir, file.replace(/\.svg$/, ".png")) });
    await page.close();
    console.log(`${file}: ${width}x${height}`);
  }
} finally { await browser.close(); }
