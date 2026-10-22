import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 820, height: 1200 }, deviceScaleFactor: 2 });
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.html");
await page.waitForTimeout(600);
await page.screenshot({ path: "C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.png", fullPage: true });
await browser.close();
console.log("ok");
