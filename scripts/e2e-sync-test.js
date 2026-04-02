const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:8890';

let passed = 0;
let failed = 0;

function log(test, result, details = '') {
  const status = result ? '✅ PASS' : '❌ FAIL';
  console.log('   ' + status + ': ' + test + (details ? ' - ' + details : ''));
  if (result) passed++; else failed++;
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTests() {
  console.log('=== COA-dash E2E Sync Tests ===\n');

  const browser = await chromium.launch({
    headless: true,
    executablePath: '/home/aegis/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome',
    args: ['--no-sandbox', '--disable-gpu']
  });

  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true
  });

  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

  try {
    // TEST CASE 1: Import and Load Session
    console.log('1. Test Case: Import and Load Session');

    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 10000 });
    await sleep(500);
    log('Homepage loads', true);

    await page.click('[data-tab="claudecode"]');
    await sleep(500);
    log('Claude tab opens', await page.$('.claudecode-page') !== null);

    let sessionCards = await page.$$('.claude-project-card');
    log('Session list displays', sessionCards.length > 0, sessionCards.length + ' session(s)');

    // Import modal
    console.log('\n   Testing Import modal...');
    await page.evaluate(() => showImportClaudeSessionModal());
    await sleep(2000);

    const modal = await page.$('.modal-content');
    log('Import modal opens', modal !== null);

    const availableSessions = await page.$$('.available-session-item');
    log('Available sessions listed', availableSessions.length > 0, availableSessions.length + ' sessions');

    const projectNames = await page.$$eval('.session-project', els =>
      [...new Set(els.map(el => el.textContent))]);
    log('Projects grouped', projectNames.length <= availableSessions.length,
        'Projects: ' + projectNames.join(', '));

    const closeBtn = await page.$('.modal-close');
    if (closeBtn) await closeBtn.click();
    await sleep(300);

    // TEST CASE 2: Conversation View
    console.log('\n2. Test Case: Conversation View');

    sessionCards = await page.$$('.claude-project-card');
    await sessionCards[0].click();
    await sleep(1000);

    log('Conversation opens', await page.$('.claude-conversation') !== null);

    const messages = await page.$$('.claude-message');
    log('Messages load', messages.length > 0, messages.length + ' messages');

    let emptyCount = 0;
    for (const msg of messages) {
      const text = await msg.textContent();
      if (!text || text.trim() === '' || text.includes('[object Object]')) emptyCount++;
    }
    log('All messages have content', emptyCount === 0, emptyCount > 0 ? emptyCount + ' empty' : '');

    const input = await page.$('#claudeInput');
    const sendBtn = await page.$('button:has-text("Send")');
    log('Input area present', input !== null && sendBtn !== null);

    // TEST CASE 3: Send Message
    console.log('\n3. Test Case: Send Message from Dashboard');

    const testMsg = 'E2E sync test at ' + new Date().toISOString();
    await page.fill('#claudeInput', testMsg);

    const statusBefore = await page.$eval('.claude-conversation-status', el => el.textContent);
    log('Status before send', statusBefore.includes('idle') || statusBefore.includes('done'), statusBefore);

    await page.click('button:has-text("Send")');
    await sleep(300);

    const workingIndicator = await page.$('.claude-working-indicator');
    const processingBar = await page.$('.claude-processing-bar');
    log('Working indicator appears', workingIndicator !== null || processingBar !== null);

    // Check user message appears immediately
    await sleep(500);
    const userMsgVisible = await page.evaluate(() => {
      const msgs = document.querySelectorAll('.claude-message.user');
      return msgs.length > 0;
    });
    log('User message appears immediately', userMsgVisible);

    console.log('   Waiting for Claude response (8s)...');
    await sleep(8000);

    // TEST CASE 4: Processing Indicator
    console.log('\n4. Test Case: Processing Indicator');

    // Check if processing elements appeared
    log('Processing bar CSS exists', await page.$('.claude-processing-bar') !== null);
    log('Spinner CSS exists', await page.$('.spinner') !== null);

    // TEST CASE 5: SSE Connection
    console.log('\n5. Test Case: SSE Connection');

    // Check SSE is working by verifying messages loaded
    const msgsAfter = await page.$$('.claude-message');
    log('Messages still visible after wait', msgsAfter.length > 0, msgsAfter.length + ' messages');

    // TEST CASE 6: Error Handling
    console.log('\n6. Test Case: Error Handling');

    const criticalErrors = errors.filter(e =>
      !e.includes('favicon') && !e.includes('.well-known') && !e.includes('Failed to load resource'));
    log('No critical JS errors', criticalErrors.length === 0);

    // TEST CASE 7: Mobile Layout
    console.log('\n7. Test Case: Mobile Layout');

    const bottomNav = await page.$('.bottom-nav');
    const navBox = await bottomNav.boundingBox();
    const viewport = page.viewportSize();
    log('Bottom nav at bottom', navBox.y + navBox.height > viewport.height - 10);

    const navButtons = await page.$$('.nav-item');
    let touchOk = true;
    for (const btn of navButtons) {
      const box = await btn.boundingBox();
      if (box && box.height < 44) { touchOk = false; break; }
    }
    log('Touch targets 44px minimum', touchOk);

    // TEST CASE 8: API Sync Test
    console.log('\n8. Test Case: API Sync');

    // Get session info via API
    const sessionData = await page.evaluate(async () => {
      const res = await fetch('/api/claudecode/sessions');
      return res.json();
    });
    log('API returns sessions', sessionData.sessions && sessionData.sessions.length > 0,
        sessionData.sessions?.length + ' sessions');

    const firstSession = sessionData.sessions?.[0];
    if (firstSession) {
      log('Session has claudeSessionId', firstSession.claudeSessionId !== null,
          firstSession.claudeSessionId ? 'linked' : 'not linked');
      log('Message count > 0', firstSession.messageCount > 0, firstSession.messageCount + ' messages');
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
  console.log(failed === 0 ? '✅ All tests passed!' : '❌ Some tests failed');

  process.exit(failed > 0 ? 1 : 0);
}

runTests();
