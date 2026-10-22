import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({ viewport: { width: 820, height: 1000 }, deviceScaleFactor: 2 });
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.html");
await page.waitForTimeout(500);
const letters = page.locator(".letter");
const n = await letters.count();
for (let i = 0; i < n; i++) {
  await letters.nth(i).screenshot({ path: `C:/Users/skya/.zcode/workspace/default/eidolon-deploy/card-${i + 1}.png` });
}
await browser.close();
console.log("cards:", n);
