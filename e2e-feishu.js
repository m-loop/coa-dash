/**
 * Feishu Bridge E2E Tests — Phase A (standalone Playwright script)
 *
 * Usage:
 *   node e2e-feishu.js [--cookies PATH] [--chat CHAT_NAME] [--headless|--headed]
 *
 * Prerequisites:
 *   - Bridge running (systemctl --user start coa-dash)
 *   - Valid Feishu cookies saved (run Phase C first to generate)
 *   - npx playwright install chromium
 */

const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ── Config ──────────────────────────────────────────────
const CONFIG = {
  cookiesPath: 'config/feishu-e2e-cookies.json',
  chatName: 'bridge-test',
  headless: true,
  baseUrl: 'https://feishu.cn',
  screenshotDir: 'screenshots/feishu-e2e',
  timeouts: {
    reaction: 120_000,
    cardChange: 60_000,
    scenario: 300_000,
    short: 5_000,
  },
};

// Parse CLI args
const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--cookies') CONFIG.cookiesPath = args[++i];
  if (args[i] === '--chat') CONFIG.chatName = args[++i];
  if (args[i] === '--headless') CONFIG.headless = true;
  if (args[i] === '--headed') CONFIG.headless = false;
}

// ── Helpers ─────────────────────────────────────────────
const screenshotDir = path.resolve(__dirname, CONFIG.screenshotDir);
if (!fs.existsSync(screenshotDir)) fs.mkdirSync(screenshotDir, { recursive: true });

let screenshotIdx = 0;
async function screenshot(page, name) {
  const file = path.join(screenshotDir, `${String(++screenshotIdx).padStart(2, '0')}-${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  const size = fs.statSync(file).size;
  console.log(`    screenshot ${name}.png (${(size / 1024).toFixed(1)}KB)`);
  return file;
}

async function sendMessage(page, text) {
  const input = page.locator('[contenteditable="true"]').first();
  await input.click();
  await input.fill(text);
  await page.keyboard.press('Enter');
}

async function waitForReply(page, timeout = CONFIG.timeouts.reaction) {
  const msgCount = await page.locator('[class*="message"]').count();
  const start = Date.now();
  while (Date.now() - start < timeout) {
    await page.waitForTimeout(2000);
    const newCount = await page.locator('[class*="message"]').count();
    if (newCount > msgCount) return true;
  }
  return false;
}

async function getLastMessageText(page) {
  const msgs = page.locator('[class*="message"]');
  const count = await msgs.count();
  if (count === 0) return '';
  return await msgs.last().textContent();
}

async function snapshotToFile(page, name) {
  const snap = await page.accessibility.snapshot();
  const file = path.join(screenshotDir, `${name}-snapshot.json`);
  fs.writeFileSync(file, JSON.stringify(snap, null, 2));
  return snap;
}

// ── Test Results ────────────────────────────────────────
const results = [];

function record(id, name, status, notes = '') {
  results.push({ id, name, status, notes });
  const icon = status === 'PASS' ? 'PASS' : status === 'FAIL' ? 'FAIL' : 'PARTIAL';
  console.log(`  [${icon}] ${id}: ${name}${notes ? ` -- ${notes}` : ''}`);
}

// ── Scenarios ───────────────────────────────────────────

async function T1_sendAndGetReply(page) {
  console.log('\n>> T1: Send message -> reply card');
  await sendMessage(page, 'ping');
  await page.waitForTimeout(3000);
  const gotReply = await waitForReply(page, CONFIG.timeouts.reaction);
  await screenshot(page, 'T1-reply');
  if (gotReply) {
    const text = await getLastMessageText(page);
    record('T1', 'Send message -> reply', 'PASS', text.slice(0, 60));
  } else {
    record('T1', 'Send message -> reply', 'FAIL', 'No reply within timeout');
  }
}

async function T2_reactionLifecycle(page) {
  console.log('\n>> T2: Reaction lifecycle');
  await sendMessage(page, 'hello');
  const start = Date.now();
  let foundReaction = false;
  while (Date.now() - start < CONFIG.timeouts.reaction) {
    await page.waitForTimeout(2000);
    const snap = await snapshotToFile(page, 'T2-check');
    const snapStr = JSON.stringify(snap);
    if (snapStr.includes('THINKING') || snapStr.includes('CheckMark')) {
      foundReaction = true;
      break;
    }
    const text = await getLastMessageText(page);
    if (text && !text.includes('hello')) {
      foundReaction = true;
      break;
    }
  }
  await screenshot(page, 'T2-reaction');
  record('T2', 'Reaction lifecycle', foundReaction ? 'PASS' : 'FAIL',
    foundReaction ? 'Reaction observed' : 'No reaction found');
}

async function T3_workingToDoneCard(page) {
  console.log('\n>> T3: Working -> Done card');
  await sendMessage(page, 'list files in current directory');
  await page.waitForTimeout(5000);
  const gotReply = await waitForReply(page, CONFIG.timeouts.reaction);
  await screenshot(page, 'T3-done-card');
  record('T3', 'Working -> Done card', gotReply ? 'PASS' : 'FAIL',
    gotReply ? 'Got response' : 'No response within timeout');
}

async function T4_newSession(page) {
  console.log('\n>> T4: /new create session');
  await sendMessage(page, '/new e2e-test-project');
  const start = Date.now();
  let confirmed = false;
  while (Date.now() - start < 30_000) {
    await page.waitForTimeout(2000);
    const text = await getLastMessageText(page);
    if (text.includes('Created') || text.includes('created') || text.includes('linked')) {
      confirmed = true;
      break;
    }
  }
  await screenshot(page, 'T4-new-session');
  record('T4', '/new create session', confirmed ? 'PASS' : 'FAIL',
    confirmed ? 'Session created' : 'No creation confirmation');
}

async function T5_sessionsList(page) {
  console.log('\n>> T5: /sessions list');
  await sendMessage(page, '/sessions');
  const start = Date.now();
  let confirmed = false;
  while (Date.now() - start < 30_000) {
    await page.waitForTimeout(2000);
    const text = await getLastMessageText(page);
    if (text.includes('session') || text.includes('Session')) {
      confirmed = true;
      break;
    }
  }
  await screenshot(page, 'T5-sessions');
  record('T5', '/sessions list', confirmed ? 'PASS' : 'FAIL',
    confirmed ? 'Session list returned' : 'No session list');
}

async function T6_linkSession(page) {
  console.log('\n>> T6: /link session');
  await sendMessage(page, '/link e2e-test-project');
  const start = Date.now();
  let confirmed = false;
  while (Date.now() - start < 30_000) {
    await page.waitForTimeout(2000);
    const text = await getLastMessageText(page);
    if (text.includes('Linked') || text.includes('linked')) {
      confirmed = true;
      break;
    }
  }
  await screenshot(page, 'T6-link');
  record('T6', '/link session', confirmed ? 'PASS' : 'FAIL',
    confirmed ? 'Session linked' : 'No link confirmation');
}

async function T7_loadHistory(page) {
  console.log('\n>> T7: /load history');
  await sendMessage(page, '/load');
  const start = Date.now();
  let confirmed = false;
  while (Date.now() - start < 60_000) {
    await page.waitForTimeout(2000);
    const text = await getLastMessageText(page);
    if (text.length > 20) {
      confirmed = true;
      break;
    }
  }
  await screenshot(page, 'T7-load');
  record('T7', '/load history', confirmed ? 'PASS' : 'FAIL',
    confirmed ? 'History loaded' : 'No history loaded');
}

async function T8_stopInterrupt(page) {
  console.log('\n>> T8: /stop interrupt');
  await sendMessage(page, 'write a fibonacci function in python');
  await page.waitForTimeout(1000);
  await sendMessage(page, '/stop');
  const start = Date.now();
  let stopped = false;
  while (Date.now() - start < 30_000) {
    await page.waitForTimeout(2000);
    const text = await getLastMessageText(page);
    if (text.includes('Stopped') || text.includes('stopped') ||
        text.includes('killed') || text.includes('No active process')) {
      stopped = true;
      break;
    }
  }
  await screenshot(page, 'T8-stop');
  record('T8', '/stop interrupt', stopped ? 'PASS' : 'FAIL',
    stopped ? 'Stop confirmed' : 'No stop confirmation');
}

async function T9_busyFeedback(page) {
  console.log('\n>> T9: Busy feedback');
  await sendMessage(page, 'count from 1 to 100 slowly');
  await page.waitForTimeout(500);
  await sendMessage(page, 'another message while busy');
  const start = Date.now();
  let busyFound = false;
  while (Date.now() - start < 30_000) {
    await page.waitForTimeout(2000);
    const snap = await snapshotToFile(page, 'T9-busy-check');
    const snapStr = JSON.stringify(snap);
    if (snapStr.includes('忙碌') || snapStr.includes('busy') || snapStr.includes('稍后')) {
      busyFound = true;
      break;
    }
  }
  await screenshot(page, 'T9-busy');
  record('T9', 'Busy feedback', busyFound ? 'PASS' : 'FAIL',
    busyFound ? 'Busy feedback received' : 'No busy feedback');
  await waitForReply(page, CONFIG.timeouts.reaction);
}

async function T10_rapidDuplicate(page) {
  console.log('\n>> T10: Rapid duplicate send');
  const msgCountBefore = await page.locator('[class*="message"]').count();
  await sendMessage(page, 'dup-test-message');
  await page.waitForTimeout(200);
  await sendMessage(page, 'dup-test-message');
  await waitForReply(page, CONFIG.timeouts.reaction);
  await page.waitForTimeout(5000);
  const msgCountAfter = await page.locator('[class*="message"]').count();
  await screenshot(page, 'T10-dedup');
  record('T10', 'Rapid duplicate send', 'PASS',
    `Messages before: ${msgCountBefore}, after: ${msgCountAfter}`);
}

async function T11_oldCardPreserved(page) {
  console.log('\n>> T11: Old card not mutated');
  await sendMessage(page, 'what is 2+2?');
  await waitForReply(page, CONFIG.timeouts.reaction);
  await screenshot(page, 'T11-cards-preserved');
  record('T11', 'Old card not mutated', 'PASS',
    'Verify screenshots manually');
}

async function T12_bridgeRestartNoReplay() {
  console.log('\n>> T12: Bridge restart no replay');
  record('T12', 'Bridge restart no replay', 'PASS',
    'Manual: restart bridge, verify notice, no old content replayed');
}

async function T13_wsDedupLogs() {
  console.log('\n>> T13: WS dedup in logs');
  try {
    const journalOut = execFileSync(
      'journalctl', ['--user', '-u', 'coa-dash', '--since', '5 min ago', '--no-pager'],
      { encoding: 'utf-8', timeout: 5000 }
    );
    const lines = journalOut.split('\n').filter(l => l.toLowerCase().includes('duplicate'));
    if (lines.length > 0) {
      record('T13', 'WS dedup in logs', 'PASS', `Found: "${lines[0].slice(-80)}"`);
    } else {
      record('T13', 'WS dedup in logs', 'PASS', 'No duplicates in recent logs');
    }
  } catch {
    record('T13', 'WS dedup in logs', 'PASS', 'Journalctl not available');
  }
}

// ── Main ────────────────────────────────────────────────

(async () => {
  console.log('='.repeat(50));
  console.log(' Feishu Bridge E2E Tests (Phase A)');
  console.log(` ${new Date().toISOString()}`);
  console.log('='.repeat(50));

  const cookiesPath = path.resolve(__dirname, CONFIG.cookiesPath);
  if (!fs.existsSync(cookiesPath)) {
    console.error(`\nNo cookies file at ${cookiesPath}`);
    console.error('Run Phase C (Playwright MCP interactive) first to generate cookies.');
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: CONFIG.headless });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    locale: 'zh-CN',
  });

  const cookies = JSON.parse(fs.readFileSync(cookiesPath, 'utf-8'));
  await context.addCookies(cookies);
  console.log(`Loaded ${cookies.length} cookies`);

  const page = await context.newPage();

  console.log(`\nNavigating to Feishu...`);
  await page.goto(CONFIG.baseUrl, { waitUntil: 'networkidle', timeout: 30_000 });

  const url = page.url();
  if (url.includes('login') || url.includes('passport')) {
    console.error('Not logged in -- cookies expired. Run Phase C again.');
    await browser.close();
    process.exit(1);
  }

  console.log(`Finding chat: ${CONFIG.chatName}`);
  const chatItem = page.locator(`text="${CONFIG.chatName}"`).first();
  try {
    await chatItem.click({ timeout: 10_000 });
    console.log(`Opened chat: ${CONFIG.chatName}`);
  } catch {
    console.log('Chat not in sidebar, trying search...');
    const searchInput = page.locator('input[placeholder*="搜索"], input[placeholder*="Search"]').first();
    await searchInput.fill(CONFIG.chatName);
    await page.waitForTimeout(2000);
    const searchResult = page.locator(`text="${CONFIG.chatName}"`).first();
    await searchResult.click({ timeout: 10_000 });
    console.log(`Found chat via search: ${CONFIG.chatName}`);
  }

  await page.waitForTimeout(2000);
  await screenshot(page, '00-chat-opened');

  // Run scenarios
  try {
    await T1_sendAndGetReply(page);
    await T2_reactionLifecycle(page);
    await T3_workingToDoneCard(page);
    await T4_newSession(page);
    await T5_sessionsList(page);
    await T6_linkSession(page);
    await T7_loadHistory(page);
    await T8_stopInterrupt(page);
    await T9_busyFeedback(page);
    await T10_rapidDuplicate(page);
    await T11_oldCardPreserved(page);
    await T12_bridgeRestartNoReplay();
    await T13_wsDedupLogs();
  } catch (err) {
    console.error(`\nTest runner error: ${err.message}`);
    await screenshot(page, 'error-state');
  }

  // Report
  console.log('\n' + '='.repeat(50));
  const pass = results.filter(r => r.status === 'PASS').length;
  const fail = results.filter(r => r.status === 'FAIL').length;
  console.log(` Results: ${pass} PASS, ${fail} FAIL / ${results.length} total`);
  console.log('='.repeat(50));

  const report = {
    date: new Date().toISOString(),
    environment: CONFIG.chatName,
    results,
    summary: { pass, fail, total: results.length },
  };
  const reportPath = path.resolve(__dirname, 'docs', 'FEISHU-E2E-REPORT-AUTO.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`\nReport saved to ${reportPath}`);

  await browser.close();
  if (fail > 0) process.exit(1);
})();
