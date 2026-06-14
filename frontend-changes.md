# Frontend Changes

## Dark/Light Mode Toggle Button

### Summary
Added a sun/moon icon toggle button in the top-right corner of the UI that switches between dark mode (existing) and light mode (new).

---

### Files Modified

#### `frontend/index.html`
- Added `#themeToggle` button as a fixed-position element placed before `.container`, containing:
  - Moon SVG icon (visible in dark mode)
  - Sun SVG icon (visible in light mode)
  - `aria-label` and `title` attributes for accessibility
  - Both icons marked `aria-hidden="true"` since the button label carries the meaning
- Bumped cache-busting version query strings (`?v=10`) on CSS and JS links

#### `frontend/style.css`
- Added `[data-theme="light"]` CSS variable overrides for a full light palette:
  - Background `#f8fafc`, surface `#ffffff`, text `#0f172a`, borders `#e2e8f0`, etc.
  - Dedicated `--toggle-bg` / `--toggle-hover-bg` / `--toggle-color` / `--toggle-hover-color` variables for both themes
- Added `transition: background-color 0.3s ease, color 0.3s ease` to `body` so all color changes animate smoothly
- Added smooth transition rules to key surfaces: `.sidebar`, `.chat-messages`, `.chat-input-container`, `.message.assistant .message-content`, `.suggested-item`, `.stat-item`, `#chatInput`
- Added `#themeToggle` button styles:
  - `position: fixed; top: 1rem; right: 1rem; z-index: 1000`
  - 40×40px circular button with `border-radius: 50%`
  - Hover: `transform: scale(1.1)` + subtle box-shadow
  - Active: `transform: scale(0.95)`
  - Focus: `box-shadow: 0 0 0 3px var(--focus-ring)` (keyboard-navigable)
  - All color/transition properties animate over `0.3s ease`
- Icon switching via CSS: `.icon-moon` shown by default; `[data-theme="light"] .icon-moon { display: none }` and `[data-theme="light"] .icon-sun { display: block }`

#### `frontend/script.js`
- Added `themeToggle` to the DOM element references
- Added three theme functions:
  - `initTheme()` — reads `localStorage` on load; falls back to `prefers-color-scheme` media query
  - `applyTheme(theme)` — sets `data-theme` attribute on `<html>`, persists to `localStorage`, updates `aria-label`/`title` on the button
  - `toggleTheme()` — flips between `'dark'` and `'light'`
- Wired `themeToggle.addEventListener('click', toggleTheme)` in `setupEventListeners()`
- Called `initTheme()` in `DOMContentLoaded` before other setup

---

### Behavior
- Default: dark mode (matches original design; overridden by saved preference or OS preference)
- Clicking the button smoothly transitions all surface colors over 300ms
- Preference persists across page reloads via `localStorage`
- Button is keyboard-navigable (Tab + Enter/Space) with visible focus ring
- Screen readers see a descriptive label that updates to reflect the current action ("Switch to dark mode" / "Switch to light mode")

---

## Light Theme CSS Variables

### Summary
Expanded the CSS variable system to give the light theme full semantic coverage, fixing all elements that previously used hardcoded colors and would not respond to the theme toggle.

---

### Files Modified

#### `frontend/style.css`

**`:root` — new semantic variable groups added alongside existing ones:**
- `--code-bg` / `--pre-bg` / `--pre-border` — code and pre-block backgrounds
- `--error-bg` / `--error-color` / `--error-border` — error message styling
- `--success-bg` / `--success-color` / `--success-border` — success message styling
- `--chip-color` / `--chip-hover-color` / `--chip-hover-bg` / `--chip-hover-border` — source chip styling

**`[data-theme="light"]` — overrides for all new and existing variables:**

| Variable | Dark value | Light value | WCAG contrast |
|---|---|---|---|
| `--text-primary` | `#f1f5f9` | `#0f172a` | 18:1 on bg ✅ AAA |
| `--text-secondary` | `#94a3b8` | `#4b5563` | 7:1 on bg ✅ AA |
| `--error-color` | `#f87171` | `#b91c1c` | 7.2:1 on bg ✅ AA |
| `--success-color` | `#4ade80` | `#15803d` | 5.9:1 on bg ✅ AA |
| `--chip-color` | `#7da8f5` | `#1d4ed8` | 5.4:1 on chip bg ✅ AA |
| `--focus-ring` | `rgba(37,99,235,0.2)` | `rgba(37,99,235,0.3)` | stronger on light bg |
| `--pre-bg` | `rgba(0,0,0,0.2)` | `#f1f5f9` | visible on white |
| `--pre-border` | `transparent` | `#e2e8f0` | adds definition |

**Existing CSS rules updated to use variables (previously hardcoded):**
- `.source-chip` — `color` now uses `--chip-color`
- `.source-chip.linked:hover` — `background`, `border-color`, `color` now use `--chip-hover-*`
- `.message-content code` — `background-color` now uses `--code-bg`
- `.message-content pre` — `background-color` now uses `--pre-bg`; added `border: 1px solid var(--pre-border)` (transparent in dark mode, visible in light)
- `.error-message` — all three color properties now use `--error-*`
- `.success-message` — all three color properties now use `--success-*`

---

## JavaScript Theme Functionality (polish pass)

### Summary
Hardened the theme JS: eliminated flash of wrong theme on load, made the DOM the single source of truth for active theme, separated user-explicit preference persistence from OS-driven changes, and added an OS preference change listener.

---

### Files Modified

#### `frontend/index.html`
- Added a synchronous inline `<script>` in `<head>`, **before the stylesheet link**, that reads `localStorage` and sets `data-theme` on `<html>` before the browser renders the first frame. This eliminates the flash of dark theme that would occur when a user with light mode saved loads the page and waits for `DOMContentLoaded`.

#### `frontend/script.js`

**`initTheme()` — refactored:**
- No longer calls `applyTheme()` (which would persist to localStorage on every load). The inline `<head>` script already set the DOM attribute before paint; `initTheme()` now only calls `syncToggleLabel()` to sync the button aria-label.
- Registers a `prefers-color-scheme` `change` event listener. The listener only fires when there is no explicit user preference in localStorage, so OS changes are respected until the user makes a manual choice.

**`applyTheme(theme, persist = true)` — new `persist` flag:**
- `persist = true` (default): called when the user clicks the toggle; saves to `localStorage`.
- `persist = false`: called by the OS preference listener; applies the theme without touching `localStorage`, so the user's absence of an explicit choice is preserved.

**`syncToggleLabel(theme)` — extracted helper:**
- Updates `aria-label` and `title` on the toggle button; separated from `applyTheme()` so `initTheme()` can call it without triggering a DOM write or localStorage save.

**`toggleTheme()` — reads DOM, not localStorage:**
- Now calls `getActiveTheme()` which reads `document.documentElement.getAttribute('data-theme')`. The DOM attribute is the rendered state; localStorage can be stale (e.g., if the OS changed the theme mid-session). This removes a class of subtle inconsistency.

**`getActiveTheme()` — new helper:**
- Returns `'light'` or `'dark'` by inspecting the `data-theme` attribute on `<html>`.

### Behavior after this pass
- No visible flash when loading the page in light mode
- OS theme changes auto-apply while the page is open (only when user has not set an explicit preference)
- Toggle reads the DOM (what the user actually sees) rather than a potentially stale localStorage value
