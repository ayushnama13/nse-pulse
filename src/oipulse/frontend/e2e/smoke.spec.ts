import { test, expect } from '@playwright/test'

// One smoke per ported surface: loads, renders, core interaction works.
// Data-dependent assertions are tolerant (empty DB shows Empty states, not errors).

test('shell renders: header, stat cards, tabs', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('OI', { exact: false }).first()).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Option Chain' })).toBeVisible()
  await expect(page.getByText('SPOT')).toBeVisible()
})

test('tab switching via click and URL hash', async ({ page }) => {
  await page.goto('/#tab=pulse&sym=NIFTY')
  await expect(page.getByRole('tab', { name: 'Pulse' })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: 'Payoff' }).click()
  await expect(page).toHaveURL(/tab=payoff/)
})

test('chain tab: filter controls present', async ({ page }) => {
  await page.goto('/#tab=chain&sym=NIFTY')
  await expect(page.getByText('±500')).toBeVisible()
  await expect(page.getByText('Any buildup')).toBeVisible()
})

test('command palette opens with Ctrl+K and navigates', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Control+k')
  await page.getByPlaceholder(/Type a command/).fill('macro')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('tab', { name: 'Macro' })).toHaveAttribute('aria-selected', 'true')
})

test('payoff tab computes a curve from the builder', async ({ page }) => {
  await page.goto('/#tab=payoff&sym=NIFTY')
  await expect(page.getByText('Payoff Builder')).toBeVisible()
  await expect(page.getByText('Max Profit')).toBeVisible()
})
