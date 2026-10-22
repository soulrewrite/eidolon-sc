import { chromium } from "playwright";
const browser = await chromium.launch({ channel: "msedge" });
const page = await browser.newPage({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
});
await page.goto("file:///C:/Users/skya/.zcode/workspace/default/eidolon-deploy/preview-letters.html");
await page.waitForTimeout(600);
// 每封信在手机上的样子（日文那张纸）
const sheets = page.locator(".letter .sheet:not(.zh)");
const n = await sheets.count();
for (let i = 0; i < n; i++) {
  await sheets.nth(i).screenshot({ path: `C:/Users/skya/.zcode/workspace/default/eidolon-deploy/phone-${i + 1}.png` });
}
await page.screenshot({ path: "C:/Users/skya/.zcode/workspace/default/eidolon-deploy/phone-top.png" });
await browser.close();
console.log("phone cards:", n);
