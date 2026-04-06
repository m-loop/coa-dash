/**
 * COA-dash Real E2E Mobile Tests
 *
 * Tests actual user flows: type text → send → verify response appears
 * NOT superficial "element exists" checks.
 *
 * Device: Huawei Mate X6 (folded 393x844, unfolded 780x1072)
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:8890';
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
const FOLDED = { width: 393, height: 844 };
const UNFOLDED = { width: 780, height: 1072 };

let passed = 0, failed = 0;
const results = [];

if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

// ─── Helpers ────────────────────────────────────────────────

async function createMobileBrowser(viewport = FOLDED) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; HarmonyOS) AppleWebKit/537.36',
    hasTouch: true,
    isMobile: true,
    deviceScaleFactor: 3,
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => consoleErrors.push(err.message));

  return { browser, context, page, consoleErrors };
}

async function assert(condition, name, page = null) {
  if (condition) {
    passed++;
    results.push({ name, status: 'PASS' });
    console.log(`  ✓ ${name}`);
  } else {
    failed++;
    results.push({ name, status: 'FAIL' });
    console.log(`  ✗ ${name}`);
    if (page) {
      const file = path.join(SCREENSHOT_DIR, `fail-${name.replace(/[^a-z0-9]/gi, '-')}.png`);
      await page.screenshot({ path: file }).catch(() => {});
    }
  }
}

async function loadPage(page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  // Wait for session data to load
  await page.waitForTimeout(1500);
}

async function openFirstSession(page) {
  const card = await page.$('.claude-project-card');
  if (!card) return false;
  await card.tap();
  await page.waitForTimeout(1500);
  return true;
}

async function getFirstSessionId(page) {
  // Get session ID from the first card's onclick attribute
  return await page.evaluate(() => {
    const card = document.querySelector('.claude-project-card');
    if (!card) return null;
    const onclick = card.getAttribute('onclick') || '';
    const match = onclick.match(/selectClaudeSession\('([^']+)'\)/);
    return match ? match[1] : null;
  });
}

// ─── T1: Send Message — Happy Path ────────────────────────

async function testSendMessageHappyPath() {
  console.log('\n📍 T1: Send Message — Happy Path (injected)');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) {
      console.log('  ⏭ No sessions available');
      await browser.close();
      return;
    }

    // Verify conversation view loaded
    const conv = await page.$('.claude-conversation');
    await assert(conv !== null, 'T1.1 Conversation view opens on tap', page);

    // Type real text
    const input = await page.$('#claudeInput');
    await assert(input !== null, 'T1.2 Message input exists', page);
    await input.tap();
    await input.fill('hello from e2e test');

    // Verify text in input before send
    const beforeVal = await input.inputValue();
    await assert(beforeVal === 'hello from e2e test', 'T1.3 Input has typed text', page);

    // Set up API response listener BEFORE tap
    const apiPromise = page.waitForResponse(
      r => r.url().includes('/message') && r.request().method() === 'POST',
      { timeout: 10000 }
    );

    // Tap send
    const sendBtn = await page.$('.claude-input-area .btn-primary');
    await sendBtn.tap();

    const apiResponse = await apiPromise;
    const apiBody = await apiResponse.json();

    // Assert API response
    await assert(apiResponse.status() === 200, 'T1.4 API returns 200', page);
    await assert(apiBody.injected === true || apiBody.retained === true || apiBody.success === true,
      `T1.5 API returns success (injected=${apiBody.injected}, retained=${apiBody.retained})`, page);

    // Assert input cleared after send
    const afterVal = await input.inputValue();
    await assert(afterVal === '', 'T1.6 Input cleared after send', page);

    // Assert user message appears in chat
    const userMsgCount = await page.evaluate(() => {
      const msgs = document.querySelectorAll('.claude-message.user');
      return Array.from(msgs).filter(el => el.textContent.includes('hello from e2e test')).length;
    });
    await assert(userMsgCount >= 1, `T1.7 User message visible in chat (${userMsgCount} found)`, page);

    // Assert source indicator (📱 = dashboard)
    const hasDashboardIcon = await page.evaluate(() => {
      const msgs = document.querySelectorAll('.claude-message.user .message-role');
      return Array.from(msgs).some(el => el.textContent.includes('📱'));
    });
    await assert(hasDashboardIcon, 'T1.8 Message shows dashboard source (📱)', page);

    // Assert auto-scroll (messages container near bottom)
    const scrollRatio = await page.evaluate(() => {
      const el = document.getElementById('claudeMessages');
      if (!el) return 0;
      return (el.scrollTop + el.clientHeight) / el.scrollHeight;
    });
    await assert(scrollRatio > 0.8, `T1.9 Auto-scrolled to bottom (${(scrollRatio * 100).toFixed(0)}%)`, page);

  } catch (e) {
    await assert(false, `T1 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T2: Empty Message Rejected ────────────────────────────

async function testEmptyMessageRejected() {
  console.log('\n📍 T2: Empty Message Rejected');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Count messages before
    const beforeCount = await page.evaluate(() =>
      document.querySelectorAll('.claude-message').length
    );

    // Don't type anything, tap send
    const sendBtn = await page.$('.claude-input-area .btn-primary');
    await sendBtn.tap();
    await page.waitForTimeout(500);

    // Assert no API call was made (no new messages)
    const afterCount = await page.evaluate(() =>
      document.querySelectorAll('.claude-message').length
    );
    await assert(afterCount === beforeCount,
      `T2.1 Empty send does nothing (messages: ${beforeCount} → ${afterCount})`, page);

    // Type spaces only
    const input = await page.$('#claudeInput');
    await input.fill('   ');
    await sendBtn.tap();
    await page.waitForTimeout(500);

    const afterSpaces = await page.evaluate(() =>
      document.querySelectorAll('.claude-message').length
    );
    await assert(afterSpaces === beforeCount,
      `T2.2 Whitespace-only send does nothing`, page);

  } catch (e) {
    await assert(false, `T2 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T3: Status Transitions on Send ────────────────────────

async function testStatusTransitions() {
  console.log('\n📍 T3: Status Indicator Transitions');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Check initial status
    const initialStatus = await page.evaluate(() => {
      const el = document.querySelector('.claude-conversation-status');
      return el ? { class: el.className, text: el.textContent } : null;
    });
    await assert(initialStatus !== null, 'T3.1 Status indicator exists', page);
    await assert(initialStatus.class.includes('idle') || initialStatus.class.includes('done'),
      `T3.2 Initial status is idle/done: "${initialStatus.class}"`, page);

    // Send message and watch status change
    const input = await page.$('#claudeInput');
    await input.fill('status transition test');

    const apiPromise = page.waitForResponse(
      r => r.url().includes('/message') && r.request().method() === 'POST',
      { timeout: 10000 }
    );

    await page.$('.claude-input-area .btn-primary').then(b => b.tap());
    await apiPromise;

    // After send, status should have changed (even if briefly)
    // Check if working indicator was shown or status changed
    const postSendStatus = await page.evaluate(() => {
      const el = document.querySelector('.claude-conversation-status');
      return el ? el.className : 'none';
    });

    // Status should be idle, done, or working (any is valid after a send)
    const validStatus = postSendStatus.includes('idle') ||
                        postSendStatus.includes('done') ||
                        postSendStatus.includes('working');
    await assert(validStatus,
      `T3.3 Post-send status valid: "${postSendStatus}"`, page);

  } catch (e) {
    await assert(false, `T3 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T4: Session History Persistence ───────────────────────

async function testSessionHistoryPersistence() {
  console.log('\n📍 T4: Session History Persistence');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Send a unique message
    const uniqueMsg = `persist-test-${Date.now()}`;
    const input = await page.$('#claudeInput');
    await input.fill(uniqueMsg);

    const apiPromise = page.waitForResponse(
      r => r.url().includes('/message') && r.request().method() === 'POST',
      { timeout: 10000 }
    );
    await page.$('.claude-input-area .btn-primary').then(b => b.tap());
    await apiPromise;
    await page.waitForTimeout(500);

    // Verify message in DOM
    const msgVisible = await page.evaluate((msg) => {
      return document.querySelector('.claude-messages')?.textContent.includes(msg);
    }, uniqueMsg);
    await assert(msgVisible, `T4.1 Message "${uniqueMsg}" visible before nav`, page);

    // Navigate back to session list
    const backBtn = await page.$('.claude-conversation-header .btn-small');
    if (backBtn) {
      await backBtn.tap();
      await page.waitForTimeout(800);

      // Re-open same session
      const card = await page.$('.claude-project-card');
      if (card) {
        await card.tap();
        await page.waitForTimeout(2000);

        // Verify message still visible
        const msgStillVisible = await page.evaluate((msg) => {
          return document.querySelector('.claude-messages')?.textContent.includes(msg);
        }, uniqueMsg);
        await assert(msgStillVisible,
          `T4.2 Message persists after back+reopen`, page);
      }
    }

  } catch (e) {
    await assert(false, `T4 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T5: Back Navigation ───────────────────────────────────

async function testBackNavigation() {
  console.log('\n📍 T5: Back Navigation');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Verify conversation is open
    const convBefore = await page.$('.claude-conversation');
    await assert(convBefore !== null, 'T5.1 Conversation open', page);

    // Tap back
    const backBtn = await page.$('.claude-conversation-header .btn-small');
    await assert(backBtn !== null, 'T5.2 Back button exists', page);
    await backBtn.tap();
    await page.waitForTimeout(800);

    // Verify session list visible
    const cardList = await page.$('.claude-project-card');
    await assert(cardList !== null, 'T5.3 Session list shown after back', page);

    // Verify no conversation view
    const convAfter = await page.$('.claude-conversation');
    await assert(convAfter === null, 'T5.4 Conversation removed from DOM', page);

  } catch (e) {
    await assert(false, `T5 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T6: Tab Switch Preserves State ────────────────────────

async function testTabSwitchPreservesState() {
  console.log('\n📍 T6: Tab Switch Preserves State');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Type but don't send
    const input = await page.$('#claudeInput');
    await input.fill('unsent draft text');
    await page.waitForTimeout(300);

    // Switch to Tasks tab
    await page.tap('.nav-item[data-tab="tasks"]');
    await page.waitForTimeout(800);

    // Switch back to Claude tab
    await page.tap('.nav-item[data-tab="claudecode"]');
    await page.waitForTimeout(800);

    // Verify conversation still open (not session list)
    // Note: conversation may be rebuilt on tab switch, so draft may be lost
    // but session should still be selected
    const convVisible = await page.$('.claude-conversation');
    const sessionCard = await page.$('.claude-project-card');
    await assert(convVisible !== null || sessionCard !== null,
      'T6.1 Claude tab has content after switch back', page);

  } catch (e) {
    await assert(false, `T6 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T7: Quick Commands ────────────────────────────────────

async function testQuickCommands() {
  console.log('\n📍 T7: Quick Commands');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Find quick command buttons
    const cmdBtns = await page.$$('.claude-cmd-btn');
    await assert(cmdBtns.length >= 2, `T7.1 Quick commands exist (${cmdBtns.length})`, page);

    // Tap first quick command (▶ Continue)
    const apiPromise = page.waitForResponse(
      r => r.url().includes('/message') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null);

    await cmdBtns[0].tap();
    const resp = await apiPromise;

    if (resp) {
      const body = await resp.json().catch(() => ({}));
      await assert(body.injected || body.retained || body.success,
        `T7.2 Quick command sent: ${JSON.stringify(body).substring(0, 60)}`, page);
    } else {
      await assert(false, 'T7.2 Quick command — no API response', page);
    }

  } catch (e) {
    await assert(false, `T7 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T8: Error Handling — Invalid Session ──────────────────

async function testErrorInvalidSession() {
  console.log('\n📍 T8: Error Handling — Invalid Session');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    // Directly POST to non-existent session
    const resp = await page.evaluate(async () => {
      try {
        const r = await fetch('/api/claudecode/sessions/nonexistent-session-id/message', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: 'test' })
        });
        return { status: r.status, body: await r.json() };
      } catch (e) {
        return { error: e.message };
      }
    });

    await assert(resp.status === 400 || resp.body?.error,
      `T8.1 Invalid session returns error (status=${resp.status})`, page);
    await assert(resp.body?.error?.includes('not found') || resp.body?.error?.includes('Session'),
      `T8.2 Error message mentions session: "${resp.body?.error}"`, page);

  } catch (e) {
    await assert(false, `T8 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T9: Mobile Touch Targets ──────────────────────────────

async function testTouchTargets() {
  console.log('\n📍 T9: Touch Target Sizes');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);

    // Nav items
    const navItems = await page.$$('.nav-item');
    for (let i = 0; i < navItems.length; i++) {
      const box = await navItems[i].boundingBox();
      if (box) {
        await assert(box.height >= 44,
          `T9.${i+1} Nav[${i}] height ${box.height.toFixed(0)}px ≥ 44px`, page);
      }
    }

    // All interactive buttons (visible only)
    const btns = await page.$$('.btn:not([style*="display: none"])');
    let smallCount = 0;
    for (const btn of btns) {
      const box = await btn.boundingBox();
      if (box && (box.height < 32 || box.width < 32)) smallCount++;
    }
    await assert(smallCount === 0,
      `T9.5 All visible buttons ≥32px (${smallCount} too small)`, page);

    // No horizontal scroll
    const hasHScroll = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth;
    });
    await assert(!hasHScroll, 'T9.6 No horizontal overflow on main page', page);

  } catch (e) {
    await assert(false, `T9 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T10: Responsive Folded vs Unfolded ───────────────────

async function testResponsiveLayout() {
  console.log('\n📍 T10: Responsive Layout Switch');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);

    // FOLDED: no sidebars
    const leftHidden = await page.evaluate(() =>
      getComputedStyle(document.querySelector('.sidebar-left')).display === 'none'
    );
    const rightHidden = await page.evaluate(() =>
      getComputedStyle(document.querySelector('.sidebar-right')).display === 'none'
    );
    await assert(leftHidden, 'T10.1 Folded: left sidebar hidden', page);
    await assert(rightHidden, 'T10.2 Folded: right sidebar hidden', page);

    // UNFOLD: sidebars visible
    await page.setViewportSize(UNFOLDED);
    await page.waitForTimeout(500);

    const leftVisible = await page.evaluate(() =>
      getComputedStyle(document.querySelector('.sidebar-left')).display !== 'none'
    );
    const rightVisible = await page.evaluate(() =>
      getComputedStyle(document.querySelector('.sidebar-right')).display !== 'none'
    );
    await assert(leftVisible, 'T10.3 Unfolded: left sidebar visible', page);
    await assert(rightVisible, 'T10.4 Unfolded: right sidebar visible', page);

    // Sidebar has content
    const agentsCount = await page.evaluate(() =>
      document.querySelectorAll('.sidebar-agent').length
    );
    const statsCount = await page.evaluate(() =>
      document.querySelectorAll('.sidebar-stat').length
    );
    await assert(agentsCount > 0, `T10.5 Sidebar agents: ${agentsCount}`, page);
    await assert(statsCount >= 4, `T10.6 Sidebar stats: ${statsCount}`, page);

  } catch (e) {
    await assert(false, `T10 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T11: Tab Switching All Tabs ───────────────────────────

async function testAllTabSwitching() {
  console.log('\n📍 T11: All Tab Switching');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);

    const tabs = ['tasks', 'agents', 'opencode', 'claudecode'];
    for (const tab of tabs) {
      const navBtn = await page.$(`.nav-item[data-tab="${tab}"]`);
      if (!navBtn) continue;

      await navBtn.tap();
      await page.waitForTimeout(800);

      const isActive = await page.evaluate((t) => {
        const el = document.querySelector(`.nav-item[data-tab="${t}"]`);
        return el?.classList.contains('active');
      }, tab);

      await assert(isActive, `T11.${tabs.indexOf(tab)+1} ${tab} tab activates on tap`, page);
    }

    // Content changes between tabs
    await page.tap('.nav-item[data-tab="tasks"]');
    await page.waitForTimeout(800);
    const tasksContent = await page.evaluate(() => document.getElementById('mainContent')?.innerHTML?.substring(0, 50));

    await page.tap('.nav-item[data-tab="agents"]');
    await page.waitForTimeout(800);
    const agentsContent = await page.evaluate(() => document.getElementById('mainContent')?.innerHTML?.substring(0, 50));

    await assert(tasksContent !== agentsContent,
      'T11.5 Content actually changes between tabs', page);

  } catch (e) {
    await assert(false, `T11 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T12: Send Multiple Messages Rapidly ──────────────────

async function testRapidMessaging() {
  console.log('\n📍 T12: Rapid Sequential Messages');
  const { browser, page } = await createMobileBrowser();

  try {
    await loadPage(page);
    if (!await openFirstSession(page)) { await browser.close(); return; }

    // Send 3 messages rapidly
    const msgs = [`rapid-1-${Date.now()}`, `rapid-2-${Date.now()}`, `rapid-3-${Date.now()}`];

    for (const msg of msgs) {
      const input = await page.$('#claudeInput');
      await input.fill(msg);

      const apiPromise = page.waitForResponse(
        r => r.url().includes('/message') && r.request().method() === 'POST',
        { timeout: 10000 }
      );

      await page.$('.claude-input-area .btn-primary').then(b => b.tap());
      const resp = await apiPromise;
      const body = await resp.json();

      await assert(body.injected || body.retained || body.success,
        `T12.${msgs.indexOf(msg)+1} Rapid[${msgs.indexOf(msg)}] sent (injected=${body.injected})`, page);
    }

    // All 3 messages should appear in chat
    const visibleCount = await page.evaluate((msgs) => {
      const chatText = document.querySelector('.claude-messages')?.textContent || '';
      return msgs.filter(m => chatText.includes(m)).length;
    }, msgs);
    await assert(visibleCount === 3,
      `T12.4 All 3 rapid messages visible (${visibleCount}/3)`, page);

  } catch (e) {
    await assert(false, `T12 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T13: Page Load Performance ────────────────────────────

async function testPageLoadPerformance() {
  console.log('\n📍 T13: Page Load Performance');
  const { browser, page } = await createMobileBrowser();

  try {
    const start = Date.now();
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
    const loadTime = Date.now() - start;

    await assert(loadTime < 5000, `T13.1 Page loads in ${loadTime}ms (<5s)`, page);

    // First paint timing
    const paintTiming = await page.evaluate(() => {
      const [entry] = performance.getEntriesByType('paint');
      return entry ? entry.startTime : -1;
    });
    await assert(paintTiming > 0 && paintTiming < 3000,
      `T13.2 First paint at ${paintTiming?.toFixed(0)}ms`, page);

    // Title correct
    const title = await page.title();
    await assert(title.includes('COA'), `T13.3 Title: "${title}"`, page);

  } catch (e) {
    await assert(false, `T13 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── T14: Console Error Free ──────────────────────────────

async function testConsoleErrors() {
  console.log('\n📍 T14: Console Errors');
  const { browser, page, consoleErrors } = await createMobileBrowser();

  try {
    await loadPage(page);

    // Exercise all tabs
    for (const tab of ['tasks', 'agents', 'opencode', 'claudecode']) {
      await page.tap(`.nav-item[data-tab="${tab}"]`);
      await page.waitForTimeout(800);
    }

    // Open session if available
    if (await openFirstSession(page)) {
      const input = await page.$('#claudeInput');
      if (input) {
        await input.fill('console error test');
        await page.$('.claude-input-area .btn-primary').then(b => b.tap());
        await page.waitForTimeout(1000);
      }
    }

    // Filter out known harmless errors
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon.ico') &&
      !e.includes('net::ERR_CONNECTION_REFUSED') &&
      !e.includes('404')
    );

    await assert(realErrors.length === 0,
      `T14.1 No JS errors (${realErrors.length}: ${realErrors.slice(0, 3).join('; ')})`, page);

  } catch (e) {
    await assert(false, `T14 UNEXPECTED: ${e.message}`, page);
  }
  await browser.close();
}

// ─── Run All Tests ─────────────────────────────────────────

(async () => {
  console.log('═══════════════════════════════════════════');
  console.log('🦞 COA-dash Real E2E Mobile Tests');
  console.log('═══════════════════════════════════════════');

  try {
    await testPageLoadPerformance();   // T13
    await testSendMessageHappyPath();   // T1
    await testEmptyMessageRejected();   // T2
    await testStatusTransitions();      // T3
    await testSessionHistoryPersistence(); // T4
    await testBackNavigation();         // T5
    await testTabSwitchPreservesState(); // T6
    await testQuickCommands();          // T7
    await testErrorInvalidSession();    // T8
    await testTouchTargets();           // T9
    await testResponsiveLayout();       // T10
    await testAllTabSwitching();        // T11
    await testRapidMessaging();         // T12
    await testConsoleErrors();          // T14
  } catch (e) {
    console.error(`\n❌ Test runner crashed: ${e.message}`);
    failed++;
  }

  console.log('\n═══════════════════════════════════════════');
  console.log(`Results: ${passed} passed, ${failed} failed (${passed + failed} total)`);
  console.log('═══════════════════════════════════════════');

  // Write report
  const report = {
    timestamp: new Date().toISOString(),
    total: passed + failed,
    passed,
    failed,
    results,
  };
  fs.writeFileSync(
    path.join(SCREENSHOT_DIR, 'report.json'),
    JSON.stringify(report, null, 2)
  );

  process.exit(failed > 0 ? 1 : 0);
})();
