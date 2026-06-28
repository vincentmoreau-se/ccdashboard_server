const { chromium } = require('@playwright/test');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto('http://localhost:5180/login');
  await p.fill('input[type=password]', process.env.CCSRV_DASHBOARD_PASSWORD || 'change-me');
  await p.getByRole('button', { name: /ENTRER/ }).click();
  await p.waitForURL('http://localhost:5180/');
  await p.waitForTimeout(1500);
  await p.screenshot({ path: 'shots/warroom.png' });
  await p.getByRole('link', { name: 'HISTORIQUE' }).click();
  await p.waitForTimeout(1500);
  await p.screenshot({ path: 'shots/history.png' });
  await p.getByRole('link', { name: 'CLASSEMENT' }).click();
  await p.waitForTimeout(800);
  await p.screenshot({ path: 'shots/leaderboard.png' });
  await b.close();
  console.log('done');
})();
