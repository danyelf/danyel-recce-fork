/**
 * Playwright test script for frontend tracking instrumentation
 *
 * Tests the tab_changed event by:
 * 1. Starting the recce server
 * 2. Opening the browser
 * 3. Clicking through tabs
 * 4. Capturing console logs to verify tracking
 */

const { chromium } = require('playwright');

async function testFrontendTracking() {
  console.log('🧪 Starting Frontend Tracking Test\n');

  const browser = await chromium.launch({
    headless: false, // Show browser for debugging
    slowMo: 500,     // Slow down actions to see what's happening
  });

  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console logs
  const consoleLogs = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleLogs.push(text);
    // Show frontend tracking events in real-time
    if (text.includes('[Frontend] Tracking')) {
      console.log('✅', text);
    } else if (text.includes('trackTabChanged')) {
      console.log('📍', text);
    }
  });

  try {
    // Navigate to Recce (dev server on 3000)
    console.log('📍 Navigating to http://localhost:3000\n');
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

    // Wait for app to load
    await page.waitForTimeout(2000);

    // Close any onboarding/setup dialog that might be open
    // Try clicking "Skip" button if it exists
    try {
      const skipButton = page.locator('button:has-text("Skip")').first();
      const isVisible = await skipButton.isVisible({ timeout: 1000 }).catch(() => false);
      if (isVisible) {
        await skipButton.click();
        await page.waitForTimeout(500);
      }
    } catch (e) {
      // Dialog might not have a skip button, that's ok
    }

    console.log('🔄 Testing tab navigation...\n');

    // Click on Query tab using data-value attribute (more reliable than text)
    console.log('➡️  Clicking Query tab');
    try {
      await page.click('button[data-value="/query"]');
      await page.waitForTimeout(3000);
    } catch (e) {
      console.log('❌ Failed to click Query:', e.message);
    }

    // Click on Checklist tab using data-value attribute
    console.log('➡️  Clicking Checklist tab');
    try {
      const checklistBtn = page.locator('button[data-value="/checks"]');
      const isVisible = await checklistBtn.isVisible().catch(() => false);
      console.log('   Checklist button visible:', isVisible);
      if (isVisible) {
        console.log('   URL before click:', page.url());
        await checklistBtn.click();
        await page.waitForTimeout(1500); // Wait for click and navigation
        console.log('   URL after click:', page.url());
        await page.waitForTimeout(1500);
      } else {
        console.log('   Button not visible, trying alternative selector');
        await page.click('button:has-text("Checklist")');
        await page.waitForTimeout(3000);
      }
    } catch (e) {
      console.log('❌ Failed to click Checklist:', e.message);
    }

    // Click back to Lineage tab using data-value attribute
    console.log('➡️  Clicking Lineage tab');
    try {
      const lineageBtn = page.locator('button[data-value="/lineage"]');
      const isVisible = await lineageBtn.isVisible().catch(() => false);
      console.log('   Lineage button visible:', isVisible);
      if (isVisible) {
        console.log('   URL before click:', page.url());
        await lineageBtn.click();
        await page.waitForTimeout(1500); // Wait for click and navigation
        console.log('   URL after click:', page.url());
        await page.waitForTimeout(1500);
      } else {
        console.log('   Button not visible, trying alternative selector');
        await page.click('button:has-text("Lineage")');
        await page.waitForTimeout(3000);
      }
    } catch (e) {
      console.log('❌ Failed to click Lineage:', e.message);
    }

    // Summary
    console.log('\n📊 Test Summary:');
    console.log('Total console logs captured:', consoleLogs.length);
    console.log('All logs:', consoleLogs);
    const trackingEvents = consoleLogs.filter(log => log.includes('[Frontend] Tracking tab_changed'));
    const allTrackingLogs = consoleLogs.filter(log => log.includes('Tracking') || log.includes('trackTab'));
    console.log(`   Found ${trackingEvents.length} tab_changed events`);
    if (allTrackingLogs.length > trackingEvents.length) {
      console.log(`   Found ${allTrackingLogs.length} other tracking-related logs`);
    }

    if (trackingEvents.length > 0) {
      console.log('\n📝 Events captured:');
      trackingEvents.forEach((event, i) => {
        console.log(`   ${i + 1}. ${event}`);
      });
    }

    if (allTrackingLogs.length > 0 && allTrackingLogs.length !== trackingEvents.length) {
      console.log('\n🔍 Other tracking logs:');
      allTrackingLogs.forEach((log, i) => {
        if (!log.includes('[Frontend] Tracking tab_changed')) {
          console.log(`   ${i + 1}. ${log}`);
        }
      });
    }

    // Verify we got the expected events
    const expectedEvents = 3; // Lineage→Query, Query→Checklist, Checklist→Lineage
    if (trackingEvents.length === expectedEvents) {
      console.log(`\n✅ SUCCESS: All ${expectedEvents} tab navigation events tracked correctly!`);
    } else {
      console.log(`\n⚠️  WARNING: Expected ${expectedEvents} events, got ${trackingEvents.length}`);
    }

  } catch (error) {
    console.error('❌ Error during test:', error.message);
  } finally {
    console.log('\n🏁 Test complete. Closing browser in 3 seconds...');
    await page.waitForTimeout(3000);
    await browser.close();
  }
}

// Run the test
testFrontendTracking().catch(console.error);
