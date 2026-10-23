import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 1180, height: 900 }, deviceScaleFactor: 2 });
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/compare-letters.html");
await page.waitForTimeout(500);
await page.screenshot({ path: "C:/Users/skya/.zcode/workspace/default/eidolon-deploy/compare-letters.png", fullPage: true });
await browser.close();
console.log("ok");
