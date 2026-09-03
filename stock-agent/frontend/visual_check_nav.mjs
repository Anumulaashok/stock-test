import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 200 } });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
await page.screenshot({ path: '/private/tmp/claude-501/-Users-anumulaashok-Personal-stock-test-stock-agent/ae34ba65-c440-422a-b2c2-5cbbc2ba462c/scratchpad/mobile_nav.png' });
await browser.close();
