import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 820, height: 1000 }, deviceScaleFactor: 2 });
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.html");
await page.waitForTimeout(500);
const zh = page.locator(".sheet.zh");
await zh.nth(2).screenshot({ path: "C:/Users/skya/.zcode/workspace/default/eidolon-deploy/zh-fuyuko.png" });
await browser.close();
console.log("ok");
