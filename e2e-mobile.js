/**
 * COA-dash Mobile E2E Tests
 * Simulates Huawei Mate X6 (folded: 393x844, unfolded: 780x1072)
 */
const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:8890';
const FOLDED = { width: 393, height: 844 };
const UNFOLDED = { width: 780, height: 1072 };

let page, browser, context;
let passed = 0, failed = 0, errors = [];

async function setup(viewport) {
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({
    viewport,
    userAgent: 'Mozilla/5.0 (Linux; Android 14; HarmonyOS; NOH-AN00) AppleWebKit/537.36',
    hasTouch: true,
    isMobile: true,
  });
  page = await context.newPage();

  // Collect console errors
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(`[console] ${msg.text()}`);
  });
  page.on('pageerror', err => errors.push(`[pageerror] ${err.message}`));
}

async function teardown() {
  await browser.close();
}

function assert(condition, name) {
  if (condition) {
    passed++;
    console.log(`  ✓ ${name}`);
  } else {
    failed++;
    console.log(`  ✗ ${name}`);
  }
}

// Test 1: Page Load
async function testPageLoad() {
  console.log('\n📱 Test 1: Page Load (folded)');
  await setup(FOLDED);

  const start = Date.now();
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  const loadTime = Date.now() - start;

  const title = await page.title();
  assert(title.includes('COA'), `Title contains COA: "${title}"`);
  assert(loadTime < 5000, `Page loads in ${loadTime}ms (target <5s)`);

  // Top bar visible
  const topBar = await page.$('.top-bar');
  assert(topBar !== null, 'Top bar exists');

  // Bottom nav visible with 4 tabs
  const navItems = await page.$$('.nav-item');
  assert(navItems.length === 4, `4 nav items found: ${navItems.length}`);

  // Claude tab is active by default
  const activeTab = await page.$('.nav-item.active');
  const activeText = activeTab ? await activeTab.textContent() : '';
  assert(activeText.includes('Claude'), `Claude tab active by default: "${activeText.trim()}"`);

  await teardown();
}

// Test 2: Claude Code Tab
async function testClaudeTab() {
  console.log('\n📱 Test 2: Claude Code Tab');
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });

  // Wait for session list to load
  await page.waitForTimeout(2000);

  // Check for session cards or empty state
  const sessionCards = await page.$$('.claude-project-card');
  const emptyState = await page.$('.claude-empty');
  const header = await page.$('.claudecode-header h2');
  const headerText = header ? await header.textContent() : '';

  assert(headerText.includes('Claude'), `Claude header visible: "${headerText}"`);
  assert(sessionCards.length > 0 || emptyState !== null,
    `Sessions or empty state shown (cards: ${sessionCards.length})`);

  // Check New button exists
  const newBtn = await page.$('.btn-primary');
  assert(newBtn !== null, 'New session button exists');

  await teardown();
}

// Test 3: Tab Switching
async function testTabSwitching() {
  console.log('\n📱 Test 3: Tab Switching');
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  // Switch to Tasks tab
  await page.click('.nav-item[data-tab="tasks"]');
  await page.waitForTimeout(500);
  let activeTab = await page.$('.nav-item.active');
  let tabText = await activeTab.textContent();
  assert(tabText.includes('Tasks'), `Tasks tab active: "${tabText.trim()}"`);

  // Check filter bar visible
  const filterBar = await page.$('.filter-bar');
  assert(filterBar !== null, 'Filter bar visible on tasks page');

  // Switch to Agents tab
  await page.click('.nav-item[data-tab="agents"]');
  await page.waitForTimeout(500);
  activeTab = await page.$('.nav-item.active');
  tabText = await activeTab.textContent();
  assert(tabText.includes('Agents'), `Agents tab active: "${tabText.trim()}"`);

  // Switch back to Claude
  await page.click('.nav-item[data-tab="claudecode"]');
  await page.waitForTimeout(500);
  activeTab = await page.$('.nav-item.active');
  tabText = await activeTab.textContent();
  assert(tabText.includes('Claude'), `Claude tab restored: "${tabText.trim()}"`);

  await teardown();
}

// Test 4: Touch Targets
async function testTouchTargets() {
  console.log('\n📱 Test 4: Touch Target Sizes (≥36px)');
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  // Check nav items
  const navItems = await page.$$('.nav-item');
  for (const item of navItems) {
    const box = await item.boundingBox();
    if (box) {
      assert(box.height >= 44, `Nav item height: ${box.height.toFixed(0)}px`);
    }
  }

  // Check buttons
  const btns = await page.$$('.btn');
  let smallBtnCount = 0;
  for (const btn of btns) {
    const box = await btn.boundingBox();
    if (box && box.height < 36) smallBtnCount++;
  }
  assert(smallBtnCount === 0, `All buttons ≥36px (small: ${smallBtnCount})`);

  await teardown();
}

// Test 5: Send Message Flow
async function testSendMessage() {
  console.log('\n📱 Test 5: Send Message Flow');
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(2000);

  // Click first session to open conversation
  const sessionCard = await page.$('.claude-project-card');
  if (!sessionCard) {
    console.log('  ⏭ No sessions to test message flow');
    await teardown();
    return;
  }

  await sessionCard.click();
  await page.waitForTimeout(1500);

  // Check conversation view loaded
  const conversation = await page.$('.claude-conversation');
  assert(conversation !== null, 'Conversation view opened');

  // Check input area exists
  const input = await page.$('#claudeInput');
  assert(input !== null, 'Message input exists');

  // Type a message
  await input.fill('E2E test message from mobile');

  // Check send button exists
  const sendBtn = await page.$('.claude-input-area .btn-primary');
  assert(sendBtn !== null, 'Send button exists');

  // Click send and measure response time
  const sendStart = Date.now();

  // Set up response listener
  const responsePromise = page.waitForResponse(
    resp => resp.url().includes('/message') && resp.request().method() === 'POST',
    { timeout: 10000 }
  ).catch(() => null);

  await sendBtn.click();
  const response = await responsePromise;
  const sendTime = Date.now() - sendStart;

  if (response) {
    const status = response.status();
    const body = await response.json().catch(() => ({}));
    assert(status === 200, `Send responded ${status} in ${sendTime}ms`);
    assert(body.injected || body.retained || body.success,
      `Response valid: ${JSON.stringify(body).substring(0, 80)}`);
  } else {
    // Still check that input was cleared
    const inputVal = await input.inputValue();
    assert(inputVal === '', `Input cleared after send: "${inputVal}"`);
    console.log(`  ⚠ Send response timed out (${sendTime}ms)`);
    failed++;
  }

  // Back button works
  const backBtn = await page.$('.btn-small');
  if (backBtn) {
    await backBtn.click();
    await page.waitForTimeout(500);
    const sessionList = await page.$('.claude-project-card');
    assert(sessionList !== null, 'Back to session list');
  }

  await teardown();
}

// Test 6: Unfolded Layout
async function testUnfoldedLayout() {
  console.log('\n📱 Test 6: Unfolded Layout (780px)');
  await setup(UNFOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  // Sidebars should be visible at 780px
  const leftSidebar = await page.$('.sidebar-left');
  const rightSidebar = await page.$('.sidebar-right');

  assert(leftSidebar !== null, 'Left sidebar exists');
  assert(rightSidebar !== null, 'Right sidebar exists');

  // Check left sidebar has agents
  const agentsSection = await page.$('#sidebarAgents');
  assert(agentsSection !== null, 'Sidebar agents section exists');

  // Check sidebar stats
  const statsSection = await page.$('#sidebarStats');
  assert(statsSection !== null, 'Sidebar stats section exists');

  await teardown();
}

// Test 7: No Console Errors
async function testNoConsoleErrors() {
  console.log('\n📱 Test 7: Console Error Check');
  errors = []; // reset
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(3000);

  // Switch tabs to trigger any lazy-loading errors
  for (const tab of ['tasks', 'agents', 'claudecode']) {
    const tabBtn = await page.$(`.nav-item[data-tab="${tab}"]`);
    if (tabBtn) {
      await tabBtn.click();
      await page.waitForTimeout(800);
    }
  }

  // Filter out known harmless errors
  const realErrors = errors.filter(e =>
    !e.includes('favicon.ico') &&
    !e.includes('net::ERR_CONNECTION_REFUSED') &&
    !e.includes('404')
  );

  assert(realErrors.length === 0, `No console errors (${realErrors.length}): ${realErrors.slice(0, 3).join('; ')}`);

  await teardown();
}

// Test 8: Refresh / Gateway Status
async function testRefreshButton() {
  console.log('\n📱 Test 8: Refresh Button');
  await setup(FOLDED);

  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  const refreshBtn = await page.$('#refreshBtn');
  assert(refreshBtn !== null, 'Refresh button exists');

  // Click refresh
  await refreshBtn.click();
  await page.waitForTimeout(2000);

  // Button should stop spinning
  const isLoading = await refreshBtn.evaluate(el => el.classList.contains('loading'));
  assert(!isLoading, 'Refresh spinner stopped');

  await teardown();
}

// Run all tests
(async () => {
  console.log('═══════════════════════════════════');
  console.log('🦞 COA-dash Mobile E2E Tests');
  console.log('═══════════════════════════════════');

  try {
    await testPageLoad();
    await testClaudeTab();
    await testTabSwitching();
    await testTouchTargets();
    await testSendMessage();
    await testUnfoldedLayout();
    await testNoConsoleErrors();
    await testRefreshButton();
  } catch (e) {
    console.error(`\n❌ Test runner error: ${e.message}`);
    failed++;
  }

  console.log('\n═══════════════════════════════════');
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log('═══════════════════════════════════');

  if (errors.length > 0) {
    console.log('\n📋 Console errors captured:');
    errors.forEach(e => console.log(`  - ${e}`));
  }

  process.exit(failed > 0 ? 1 : 0);
})();
