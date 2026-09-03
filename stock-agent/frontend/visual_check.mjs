import { chromium } from 'playwright';

const browser = await chromium.launch();
const viewports = {
  desktop: { width: 1280, height: 900 },
  tablet: { width: 768, height: 1024 },
  mobile: { width: 390, height: 844 },
};

for (const [name, viewport] of Object.entries(viewports)) {
  const page = await browser.newPage({ viewport });
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
  await page.getByLabel(/ticker symbol/i).fill('DANLAW');
  await page.getByRole('button', { name: /analyze/i }).click();
  await page.waitForSelector('#investment-summary-heading', { timeout: 90000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `/private/tmp/claude-501/-Users-anumulaashok-Personal-stock-test-stock-agent/ae34ba65-c440-422a-b2c2-5cbbc2ba462c/scratchpad/${name}.png`, fullPage: true });
  await page.close();
  console.log(`captured ${name}`);
}

await browser.close();
