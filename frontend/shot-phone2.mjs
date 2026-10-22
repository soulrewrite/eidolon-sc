import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.html");
await page.waitForTimeout(500);
await page.locator(".sheet.zh").nth(2).screenshot({ path: "C:/Users/skya/.zcode/workspace/default/eidolon-deploy/phone-zh.png" });
await browser.close();
console.log("ok");
