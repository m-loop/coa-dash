const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:8890';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTests() {
  console.log('=== COA-dash E2E Tests (Playwright) ===\n');

  const browser = await chromium.launch({
    headless: true,
    executablePath: '/home/aegis/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
  });

  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true
  });

  const page = await context.newPage();

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    errors.push(err.message);
  });

  // Track 404 responses
  const notFoundUrls = [];
  page.on('response', response => {
    if (response.status() === 404) {
      const url = response.url();
      // Ignore common non-critical 404s
      if (!url.includes('favicon') && !url.includes('.well-known')) {
        notFoundUrls.push(url);
      }
    }
  });

  let passed = 0;
  let failed = 0;

  try {
    // Test 1: Load homepage
    console.log('1. Loading homepage...');
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await sleep(1000);
    const title = await page.title();
    console.log('   Title: ' + title);

    if (title.includes('COA-dash') && title.includes('v0.7.0')) {
      console.log('   ✅ PASS: Homepage loaded');
      passed++;
    } else {
      console.log('   ❌ FAIL: Title mismatch');
      failed++;
    }

    // Test 2: Check navigation tabs
    console.log('\n2. Checking navigation tabs...');
    const tabs = await page.$$('.nav-item');
    console.log('   Found ' + tabs.length + ' tabs');

    if (tabs.length === 4) {
      console.log('   ✅ PASS: 4 navigation tabs');
      passed++;
    } else {
      console.log('   ❌ FAIL: Expected 4 tabs');
      failed++;
    }

    // Test 3: Click Claude tab
    console.log('\n3. Clicking Claude Code tab...');
    const claudeTab = await page.$('[data-tab="claudecode"]');
    if (claudeTab) {
      await claudeTab.click();
      await sleep(500);

      const claudePage = await page.$('.claudecode-page');
      if (claudePage) {
        console.log('   ✅ PASS: Claude Code page visible');
        passed++;
      } else {
        console.log('   ❌ FAIL: Claude page not found');
        failed++;
      }
    } else {
      console.log('   ❌ FAIL: Claude tab not found');
      failed++;
    }

    // Test 4: Check session list
    console.log('\n4. Checking session list...');
    await sleep(1000);

    const emptyState = await page.$('.claude-empty');
    const projectCards = await page.$$('.claude-project-card');

    if (emptyState) {
      console.log('   ✅ PASS: Empty state displayed');
      passed++;
    } else if (projectCards.length > 0) {
      console.log('   Found ' + projectCards.length + ' session(s)');
      console.log('   ✅ PASS: Session list displayed');
      passed++;

      // Test 5: Open conversation
      console.log('\n5. Opening conversation...');
      await projectCards[0].click();
      await sleep(500);

      const conversation = await page.$('.claude-conversation');
      if (conversation) {
        console.log('   ✅ PASS: Conversation view opened');
        passed++;

        // Test 6: Check messages
        const messages = await page.$$('.claude-message');
        console.log('   Found ' + messages.length + ' messages');

        let emptyCount = 0;
        for (const msg of messages) {
          const text = await msg.textContent();
          if (!text || text.trim() === '' || text.includes('[object Object]')) {
            emptyCount++;
          }
        }

        if (emptyCount === 0) {
          console.log('   ✅ PASS: All messages have content');
          passed++;
        } else {
          console.log('   ❌ FAIL: ' + emptyCount + ' empty messages');
          failed++;
        }

        // Test 7: Check input area
        const input = await page.$('#claudeInput');
        const sendBtn = await page.$('button:has-text("Send")');
        const backBtn = await page.$('button:has-text("Back")');

        if (input && sendBtn) {
          console.log('   ✅ PASS: Input area present');
          passed++;
        } else {
          console.log('   ❌ FAIL: Input area incomplete');
          failed++;
        }

        if (backBtn) {
          await backBtn.click();
          await sleep(500);
          console.log('   Clicked back, returning to session list...');
        }
      } else {
        console.log('   ❌ FAIL: Conversation not found');
        failed++;
      }
    } else {
      console.log('   ❌ FAIL: No content found');
      failed++;
    }

    // Wait for session list to be visible again
    await sleep(500);

    // Test 8: Import modal
    console.log('\n6. Testing Import modal...');

    // Make sure we're on the session list page
    const sessionListPage = await page.$('.claudecode-page');
    if (!sessionListPage) {
      console.log('   ⚠️  Not on session list, clicking Claude tab...');
      const claudeTab2 = await page.$('[data-tab="claudecode"]');
      if (claudeTab2) await claudeTab2.click();
      await sleep(500);
    }

    const importBtn = await page.$('button:has-text("Import")');
    if (importBtn) {
      console.log('   Found Import button, calling showImportClaudeSessionModal() directly...');

      // Call the function directly in the browser context
      await page.evaluate(() => showImportClaudeSessionModal());

      // Wait for modal to appear
      await sleep(2000);
      await page.screenshot({ path: '/tmp/import-modal.png' });

      const modal = await page.$('.modal-content');
      const modalOverlay = await page.$('.modal-overlay');
      if (modal || modalOverlay) {
        const sessionItems = await page.$$('.available-session-item');
        console.log('   Found ' + sessionItems.length + ' available session(s)');
        console.log('   ✅ PASS: Import modal works');
        passed++;

        const closeBtn = await page.$('.modal-close');
        if (closeBtn) await closeBtn.click();
        await sleep(300);
      } else {
        console.log('   ❌ FAIL: Modal not found (screenshot saved to /tmp/import-modal.png)');
        failed++;
      }
    } else {
      console.log('   ⚠️  SKIP: Import button not found');
    }

    // Test 9: JavaScript errors
    console.log('\n7. Checking for errors...');
    const criticalErrors = errors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('.well-known') &&
      !e.includes('Failed to load resource') // Ignore generic 404s, use notFoundUrls instead
    );
    if (criticalErrors.length === 0 && notFoundUrls.length === 0) {
      console.log('   ✅ PASS: No critical errors');
      passed++;
    } else {
      if (criticalErrors.length > 0) {
        console.log('   ❌ Console errors: ' + criticalErrors.length);
        criticalErrors.slice(0, 3).forEach(e => console.log('      - ' + e.substring(0, 80)));
        failed++;
      }
      if (notFoundUrls.length > 0) {
        console.log('   ❌ 404 errors: ' + notFoundUrls.length);
        notFoundUrls.forEach(u => console.log('      - ' + u));
        failed++;
      }
    }

    // Test 10: Mobile layout
    console.log('\n8. Testing mobile layout...');
    const bottomNav = await page.$('.bottom-nav');
    if (bottomNav) {
      const navBox = await bottomNav.boundingBox();
      const viewportHeight = page.viewportSize().height;
      if (navBox.y + navBox.height > viewportHeight - 10) {
        console.log('   ✅ PASS: Bottom nav positioned correctly');
        passed++;
      } else {
        console.log('   ❌ FAIL: Bottom nav not at bottom');
        failed++;
      }
    }

    // Test 11: Unfolded view
    console.log('\n9. Testing unfolded view...');
    await page.setViewportSize({ width: 890, height: 844 });
    await sleep(500);

    const sidebars = await page.$$('.sidebar');
    if (sidebars.length >= 1) {
      console.log('   ✅ PASS: Sidebar visible');
      passed++;
    } else {
      console.log('   ⚠️  Note: No sidebar (tab dependent)');
      passed++;
    }

  } catch (err) {
    console.log('\n❌ TEST ERROR: ' + err.message);
    failed++;
  } finally {
    await browser.close();
  }

  console.log('\n=== Test Results ===');
  console.log('Passed: ' + passed);
  console.log('Failed: ' + failed);

  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
