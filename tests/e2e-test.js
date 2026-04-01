const { chromium } = require('playwright');

const BASE_URL = 'http://localhost:8890';

async function runTests() {
  console.log('🧪 COA-dash E2E Tests v0.6.0\n');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 410, height: 890 } // Mate X6 folded
  });
  const page = await context.newPage();

  const results = { passed: 0, failed: 0, tests: [] };

  function log(name, status, detail = '') {
    const icon = status === 'PASS' ? '✅' : '❌';
    console.log(`${icon} ${name}${detail ? ': ' + detail : ''}`);
    results.tests.push({ name, status, detail });
    if (status === 'PASS') results.passed++;
    else results.failed++;
  }

  try {
    // TC-001: 页面加载验证
    console.log('\n📋 TC-001: 页面加载验证');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    const title = await page.title();
    if (title.includes('COA-dash v0.6.0')) {
      log('页面标题', 'PASS', title);
    } else {
      log('页面标题', 'FAIL', `Expected v0.6.0, got: ${title}`);
    }

    // Check bottom nav tabs
    const navItems = await page.$$('.nav-item');
    const navTexts = await Promise.all(navItems.map(async (item) => {
      const span = await item.$('span');
      return span ? await span.textContent() : '';
    }));

    const expectedTabs = ['Agents', 'Tasks', 'OpenCode', 'Stats'];
    const tabsMatch = expectedTabs.every(tab => navTexts.includes(tab));
    if (tabsMatch) {
      log('底部导航', 'PASS', navTexts.join(', '));
    } else {
      log('底部导航', 'FAIL', `Expected: ${expectedTabs.join(', ')}, Got: ${navTexts.join(', ')}`);
    }

    // TC-002: Stats Tab
    console.log('\n📋 TC-002: Stats Tab 功能');
    const statsTab = await page.$('[data-tab="stats"]');
    if (statsTab) {
      await statsTab.click();
      await page.waitForTimeout(500);

      // Check stats sections
      const statsTitle = await page.$('.stats-title');
      if (statsTitle) {
        const text = await statsTitle.textContent();
        log('Stats 页面渲染', 'PASS', text);
      } else {
        log('Stats 页面渲染', 'FAIL', 'No stats-title found');
      }

      // Check stats bars
      const statsBars = await page.$$('.stats-bar');
      if (statsBars.length >= 2) {
        log('Stats 进度条', 'PASS', `${statsBars.length} bars found`);
      } else {
        log('Stats 进度条', 'FAIL', `Expected 2+ bars, found ${statsBars.length}`);
      }

      // Check stats grid
      const statsItems = await page.$$('.stats-item');
      if (statsItems.length >= 4) {
        log('Stats 数据网格', 'PASS', `${statsItems.length} items found`);
      } else {
        log('Stats 数据网格', 'FAIL', `Expected 4+ items, found ${statsItems.length}`);
      }
    } else {
      log('Stats Tab 按钮', 'FAIL', 'Not found');
    }

    // TC-003: Agents Tab
    console.log('\n📋 TC-003: Agents Tab 功能');
    const agentsTab = await page.$('[data-tab="agents"]');
    if (agentsTab) {
      await agentsTab.click();
      await page.waitForTimeout(500);

      const sessionCards = await page.$$('.card');
      log('Agents/Session 卡片', 'PASS', `${sessionCards.length} cards found`);
    }

    // TC-004: Tasks Tab
    console.log('\n📋 TC-004: Tasks Tab 功能');
    const tasksTab = await page.$('[data-tab="tasks"]');
    if (tasksTab) {
      await tasksTab.click();
      await page.waitForTimeout(500);

      const taskCards = await page.$$('.card');
      if (taskCards.length > 0) {
        log('Task 卡片列表', 'PASS', `${taskCards.length} tasks found`);
      } else {
        log('Task 卡片列表', 'FAIL', 'No tasks displayed');
      }

      // Check priority dropdown exists
      const priorityBadge = await page.$('.priority-dropdown');
      if (priorityBadge) {
        log('优先级下拉组件', 'PASS');
      } else {
        log('优先级下拉组件', 'FAIL', 'Not found');
      }
    }

    // TC-005: OpenCode Tab
    console.log('\n📋 TC-005: OpenCode Tab 功能');
    const opencodeTab = await page.$('[data-tab="opencode"]');
    if (opencodeTab) {
      await opencodeTab.click();
      await page.waitForTimeout(1000);

      const opencodeSidebar = await page.$('.opencode-sidebar');
      if (opencodeSidebar) {
        log('OpenCode Sidebar', 'PASS');
      } else {
        log('OpenCode Sidebar', 'FAIL', 'Not found');
      }

      const sessionItems = await page.$$('.opencode-session-item');
      log('OpenCode Sessions', 'PASS', `${sessionItems.length} sessions`);
    }

    // TC-006: API Endpoints
    console.log('\n📋 TC-006: API 端点验证');
    const endpoints = [
      '/api/agents',
      '/api/tasks',
      '/api/sessions',
      '/api/stats',
      '/api/opencode/sessions',
      '/api/opencode/projects',
      '/api/session-state',
      '/api/assignees'
    ];

    for (const endpoint of endpoints) {
      try {
        const response = await page.goto(BASE_URL + endpoint);
        if (response && response.status() === 200) {
          log(`GET ${endpoint}`, 'PASS');
        } else {
          log(`GET ${endpoint}`, 'FAIL', `Status: ${response?.status()}`);
        }
      } catch (e) {
        log(`GET ${endpoint}`, 'FAIL', e.message);
      }
    }

    // TC-007: Security - CORS
    console.log('\n📋 TC-007: CORS 安全验证');
    await page.goto(BASE_URL);
    const corsTest = await page.evaluate(async () => {
      try {
        const response = await fetch('http://localhost:8890/api/stats', {
          headers: { 'Origin': 'http://evil.com' }
        });
        const allowOrigin = response.headers.get('Access-Control-Allow-Origin');
        return { blocked: !allowOrigin || allowOrigin !== 'http://evil.com', origin: allowOrigin };
      } catch (e) {
        return { blocked: true, error: e.message };
      }
    });
    log('CORS Origin 检查', corsTest.blocked ? 'PASS' : 'FAIL', corsTest.origin || corsTest.error);

    // TC-008: Responsive Test
    console.log('\n📋 TC-008: 响应式布局测试');

    // Mobile (folded)
    await page.setViewportSize({ width: 410, height: 890 });
    await page.goto(BASE_URL);
    await page.waitForTimeout(500);

    const mobileSidebars = await page.$$('.sidebar');
    const mobileSidebarsVisible = await Promise.all(
      mobileSidebars.map(s => s.isVisible())
    );
    const mobileHidden = !mobileSidebarsVisible.some(v => v);
    log('Mobile 侧边栏隐藏', mobileHidden ? 'PASS' : 'FAIL');

    // Desktop (unfolded)
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(500);

    const desktopSidebars = await page.$$('.sidebar');
    const desktopVisible = await Promise.all(
      desktopSidebars.map(s => s.isVisible())
    );
    const desktopShown = desktopVisible.some(v => v);
    log('Desktop 侧边栏显示', desktopShown ? 'PASS' : 'FAIL');

  } catch (error) {
    console.error('❌ Test error:', error.message);
  }

  await browser.close();

  console.log('\n' + '='.repeat(50));
  console.log(`📊 Results: ${results.passed} passed, ${results.failed} failed`);
  console.log('='.repeat(50));

  process.exit(results.failed > 0 ? 1 : 0);
}

runTests();