# Visual Design System

> Part of [Wish With Me Specification](../AGENTS.md)

---

## 1. Brand Personality

### 1.1 Attributes

| Attribute | Description | Visual Expression |
|-----------|-------------|-------------------|
| Celebratory | Gift-giving occasions, joy | Warm colors, rounded shapes, subtle sparkle effects |
| Trustworthy | Reliable sync, data safety | Consistent UI patterns, clear feedback states |
| Approachable | Easy for all ages | Large touch targets, clear typography, friendly icons |
| Modern | Contemporary design | Clean layouts, generous whitespace, subtle gradients |
| Playful | Gift surprise element | Micro-animations, delightful empty states |

### 1.2 Design Principles

1. **Clarity over cleverness** - Russian UI conventions favor explicit labels over icon-only interfaces
2. **Celebration without excess** - Festive touches that do not overwhelm functional content
3. **Mobile confidence** - Touch-friendly interactions that feel intentional, not cramped
4. **Offline transparency** - Users should always understand their sync state

---

## 2. Color Palette

### 2.1 Primary Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Indigo 500** (Primary) | `#6366F1` | 99, 102, 241 | Primary actions, links, active states |
| **Indigo 600** | `#4F46E5` | 79, 70, 229 | Primary hover, pressed states |
| **Indigo 700** | `#4338CA` | 67, 56, 202 | Primary active/focus |
| **Indigo 50** | `#EEF2FF` | 238, 242, 255 | Primary backgrounds, highlights |

### 2.2 Secondary Colors

| Name | Hex | Usage |
|------|-----|-------|
| **Teal 500** | `#14B8A6` | Secondary actions, accents |
| **Teal 600** | `#0D9488` | Secondary hover |
| **Amber 400** | `#FBBF24` | Gift/celebration accents, badges |

### 2.3 Semantic Colors

| State | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| **Success** | `#16A34A` | `#22C55E` | Sync complete, marked items |
| **Warning** | `#D97706` | `#F59E0B` | Offline state, pending sync |
| **Error** | `#DC2626` | `#EF4444` | Errors, destructive actions |
| **Info** | `#2563EB` | `#3B82F6` | Information, syncing state |

### 2.4 Neutral Palette

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| `--text-primary` | `#0F172A` | `#F8FAFC` | Headings, primary text |
| `--text-secondary` | `#475569` | `#94A3B8` | Secondary text, labels |
| `--text-tertiary` | `#94A3B8` | `#64748B` | Placeholder, disabled text |
| `--bg-primary` | `#FFFFFF` | `#0F172A` | Main background |
| `--bg-secondary` | `#F8FAFC` | `#1E293B` | Cards, elevated surfaces |
| `--bg-tertiary` | `#F1F5F9` | `#334155` | Hover states, subtle backgrounds |
| `--border-default` | `#E2E8F0` | `#334155` | Borders, dividers |
| `--border-subtle` | `#F1F5F9` | `#1E293B` | Subtle separators |

### 2.5 Surprise Mode Colors

| State | Color | Visual Treatment |
|-------|-------|------------------|
| Available | Default | Normal item display |
| Partially marked | `#16A34A` at 20% opacity | Subtle green tint on card |
| Fully marked | `#16A34A` at 30% opacity | Green tint + "All marked" badge |
| Marked by me | `#6366F1` border | Indigo left border (4px) |

### 2.6 CSS Variables

```scss
// /services/frontend/src/css/quasar.variables.sass

// Brand colors
$primary: #6366F1
$primary-dark: #4F46E5
$secondary: #14B8A6
$accent: #FBBF24

// Semantic colors (WCAG AA compliant)
$positive: #16A34A
$negative: #DC2626
$info: #2563EB
$warning: #D97706

// Quasar overrides
$dark: #0F172A
$dark-page: #0F172A
```

---

## 3. Typography System

### 3.1 Font Stack

```scss
// Primary font - excellent Cyrillic support
$font-family-sans: 'Inter', 'Roboto', -apple-system, BlinkMacSystemFont,
                   'Segoe UI', 'Helvetica Neue', Arial, sans-serif

// Monospace (for prices, codes)
$font-family-mono: 'JetBrains Mono', 'SF Mono', 'Roboto Mono',
                   'Consolas', monospace
```

### 3.2 Type Scale

| Token | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `--text-display` | 2.5rem (40px) | 1.2 | 700 | Hero headlines |
| `--text-h1` | 2rem (32px) | 1.25 | 700 | Page titles |
| `--text-h2` | 1.5rem (24px) | 1.33 | 600 | Section headings |
| `--text-h3` | 1.25rem (20px) | 1.4 | 600 | Card titles |
| `--text-h4` | 1.125rem (18px) | 1.44 | 600 | Subsection titles |
| `--text-body` | 1rem (16px) | 1.5 | 400 | Body text |
| `--text-body-sm` | 0.875rem (14px) | 1.5 | 400 | Secondary body text |
| `--text-caption` | 0.75rem (12px) | 1.5 | 500 | Captions, labels |
| `--text-overline` | 0.625rem (10px) | 1.6 | 600 | Overlines, badges |

### 3.3 Font Weights

| Weight | Value | Usage |
|--------|-------|-------|
| Regular | 400 | Body text, descriptions |
| Medium | 500 | Labels, captions, emphasis |
| Semi-bold | 600 | Subheadings, buttons |
| Bold | 700 | Headlines, important values |

### 3.4 Russian Typography

```scss
// Proper Russian quote marks
$quote-open: '\00AB'   // « guillemet left
$quote-close: '\00BB'  // » guillemet right

// Line length for readability
$max-line-length: 65ch

// Note: Russian text is 15-20% longer than English
// Plan for text expansion in UI elements
```

### 3.5 Responsive Typography

```scss
// Type scale as CSS custom properties
:root
  --text-display: 2.5rem
  --text-h1: 2rem
  --text-h2: 1.5rem
  --text-h3: 1.25rem
  --text-h4: 1.125rem
  --text-body: 1rem
  --text-body-sm: 0.875rem
  --text-caption: 0.75rem
  --text-overline: 0.625rem

// Mobile adjustments
@media (max-width: 599px)
  :root
    --text-display: 2rem
    --text-h1: 1.75rem
    --text-h2: 1.375rem
    --text-h3: 1.125rem
```

---

## 4. Spacing System

### 4.1 Spacing Scale (8px base)

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | Reset |
| `--space-1` | 0.25rem (4px) | Tight spacing, icon gaps |
| `--space-2` | 0.5rem (8px) | Inline elements, small gaps |
| `--space-3` | 0.75rem (12px) | Compact padding |
| `--space-4` | 1rem (16px) | Default padding, card gaps |
| `--space-5` | 1.25rem (20px) | Medium spacing |
| `--space-6` | 1.5rem (24px) | Section gaps |
| `--space-8` | 2rem (32px) | Large section gaps |
| `--space-10` | 2.5rem (40px) | Page sections |
| `--space-12` | 3rem (48px) | Major sections |
| `--space-16` | 4rem (64px) | Hero/header spacing |

### 4.2 Layout Grid

```scss
// Mobile-first breakpoints (Quasar default)
$breakpoint-xs: 0       // 0-599px (phones)
$breakpoint-sm: 600px   // 600-1023px (tablets portrait)
$breakpoint-md: 1024px  // 1024-1439px (tablets landscape)
$breakpoint-lg: 1440px  // 1440-1919px (desktop)
$breakpoint-xl: 1920px  // 1920px+ (large desktop)

// Container max-widths
$container-xs: 100%
$container-sm: 540px
$container-md: 720px
$container-lg: 960px
$container-xl: 1140px

// Card grid
$card-min-width: 300px
$card-max-width: 400px
$grid-gap: var(--space-4)
```

### 4.3 Component Sizing

| Component | Height | Padding | Touch Target |
|-----------|--------|---------|--------------|
| Button (default) | 44px | 16px horizontal | 44x44px min |
| Button (small) | 36px | 12px horizontal | 36x36px min |
| Button (large) | 52px | 20px horizontal | 52x52px |
| Input field | 48px | 16px horizontal | 48px height |
| List item | 56px min | 16px | 56x44px min |
| Bottom nav item | 56px | - | 48x48px |
| Card | auto | 16px | - |

### 4.4 Safe Areas (PWA)

```scss
:root
  --safe-area-inset-top: env(safe-area-inset-top, 0px)
  --safe-area-inset-bottom: env(safe-area-inset-bottom, 0px)
  --safe-area-inset-left: env(safe-area-inset-left, 0px)
  --safe-area-inset-right: env(safe-area-inset-right, 0px)

.q-footer
  padding-bottom: calc(var(--safe-area-inset-bottom) + 8px)
```

---

## 5. Icon System

### 5.1 Icon Specifications

| Property | Value |
|----------|-------|
| Library | Material Design Icons (MDI) v7 |
| Style | Outlined (default), Filled for active states |
| Size grid | 24x24px (default), 20x20px (small), 32x32px (large) |
| Stroke weight | 1.5px |
| Corner radius | 2px |

### 5.2 Icon Usage by Context

| Context | Style | Size | Examples |
|---------|-------|------|----------|
| Navigation | Outlined, Filled when active | 24px | `mdi-gift-outline`, `mdi-bell-outline` |
| Actions | Outlined | 24px | `mdi-share-variant-outline`, `mdi-pencil-outline` |
| Status indicators | Filled | 20px | `mdi-cloud-check`, `mdi-alert-circle` |
| Empty states | Outlined | 64px | Custom illustrations preferred |
| Buttons with text | Outlined | 20px | Left of label |

### 5.3 Custom Icons Needed

| Icon | Purpose | Description |
|------|---------|-------------|
| `wish-gift` | Brand mark | Stylized gift box with ribbon |
| `wish-surprise` | Surprise mode indicator | Gift with sparkles |
| `wish-marked` | Item marked | Checkmark over gift |
| `wish-share` | Share wishlist | Gift with arrow |

### 5.4 Icon Color States

| State | Color |
|-------|-------|
| Default | `--text-secondary` (#475569) |
| Active | `--primary` (#6366F1) |
| Success | `--positive` (#16A34A) |
| Error | `--negative` (#DC2626) |
| Disabled | `--text-tertiary` (#94A3B8) |

---

## 6. Illustration Style

### 6.1 Style Characteristics

| Property | Specification |
|----------|--------------|
| Style | Flat design with subtle depth (soft shadows) |
| Color palette | Primary (indigo), Secondary (teal), Accent (amber) + 2 neutrals max |
| Shapes | Geometric, rounded corners (8px radius) |
| Stroke | 2px consistent stroke for outlines |
| Character style | Simple, friendly figures without detailed faces |
| Mood | Optimistic, encouraging action |
| Size | 200x200px (mobile), 280x280px (desktop) |

### 6.2 Empty State Illustrations

| State | Mood | Visual Description | CTA |
|-------|------|-------------------|-----|
| **No wishlists** | Welcoming | Character holding empty gift box with sparkles | "Create your first wishlist" |
| **Empty wishlist** | Encouraging | Open gift box with dotted lines | "Add your first item" |
| **All items marked** | Celebratory | Character with confetti, wrapped gifts | "Check back later" |
| **No notifications** | Calm | Bell with "zzz" sleep indicator | None |
| **Search no results** | Helpful | Magnifying glass over empty space | "Try different search" |
| **Offline** | Reassuring | Cloud with disconnect symbol | "Changes saved locally" |
| **Error** | Apologetic | Character with "oops" expression | "Retry" button |

### 6.3 Illustration Colors

```scss
$illust-primary: #6366F1    // Main character/object
$illust-secondary: #14B8A6  // Accent elements
$illust-highlight: #FBBF24  // Sparkles, emphasis
$illust-bg-light: #EEF2FF   // Soft background shapes
$illust-neutral: #94A3B8    // Shadows, secondary elements
```

### 6.4 Implementation Notes

- Export as SVG for scalability
- Include `aria-hidden="true"` (decorative)
- Consider animated SVG for loading/syncing states
- Provide static fallback for `prefers-reduced-motion`

---

## 7. Component Styles

### 7.1 Cards

```scss
.card
  background: var(--bg-secondary)
  border-radius: 12px
  border: 1px solid var(--border-subtle)
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05)
  padding: var(--space-4)
  transition: box-shadow 0.2s ease, transform 0.2s ease

  &:hover
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1)
    transform: translateY(-2px)

  &:active
    transform: translateY(0)

.card-image
  border-radius: 8px
  aspect-ratio: 1
  object-fit: cover
  background: var(--bg-tertiary)
```

### 7.2 Buttons

```scss
// Primary button
.btn-primary
  background: var(--primary)
  color: white
  font-weight: 600
  border-radius: 8px
  padding: 0 var(--space-4)
  height: 44px
  transition: background 0.15s ease

  &:hover
    background: var(--primary-dark)

  &:active
    background: #4338CA

  &:disabled
    background: var(--bg-tertiary)
    color: var(--text-tertiary)

// Secondary button (outlined)
.btn-secondary
  background: transparent
  color: var(--primary)
  border: 1.5px solid var(--primary)
  border-radius: 8px

  &:hover
    background: rgba(99, 102, 241, 0.08)

// Ghost button
.btn-ghost
  background: transparent
  color: var(--text-secondary)

  &:hover
    background: var(--bg-tertiary)
```

### 7.3 Form Inputs

```scss
.input-field
  height: 48px
  border: 1.5px solid var(--border-default)
  border-radius: 8px
  padding: 0 var(--space-4)
  font-size: var(--text-body)
  transition: border-color 0.15s ease, box-shadow 0.15s ease

  &::placeholder
    color: var(--text-tertiary)

  &:focus
    border-color: var(--primary)
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15)
    outline: none

  &:invalid, &.error
    border-color: var(--negative)

  &:disabled
    background: var(--bg-tertiary)
    color: var(--text-tertiary)
```

### 7.4 Bottom Navigation

```scss
.bottom-nav
  height: 56px
  background: var(--bg-primary)
  border-top: 1px solid var(--border-default)
  display: flex
  justify-content: space-around
  padding-bottom: var(--safe-area-inset-bottom)

.bottom-nav-item
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  min-width: 64px
  padding: var(--space-1)
  color: var(--text-secondary)

  &.active
    color: var(--primary)

  .icon
    font-size: 24px

  .label
    font-size: var(--text-overline)
    margin-top: 2px
```

### 7.5 Skeleton Loading

```scss
.skeleton
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 25%,
    var(--bg-secondary) 50%,
    var(--bg-tertiary) 75%
  )
  background-size: 200% 100%
  animation: skeleton-shimmer 1.5s ease-in-out infinite
  border-radius: 4px

@keyframes skeleton-shimmer
  0%
    background-position: 200% 0
  100%
    background-position: -200% 0
```

---

## 8. Dark Mode

### 8.1 Strategy

```typescript
// Auto-detect system preference
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

// User preference stored in localStorage
const userPreference = localStorage.getItem('theme'); // 'light' | 'dark' | 'auto'
```

### 8.2 Color Adjustments

| Element | Light Mode | Dark Mode |
|---------|------------|-----------|
| Background | `#FFFFFF` | `#0F172A` |
| Cards | `#F8FAFC` | `#1E293B` |
| Text primary | `#0F172A` | `#F8FAFC` |
| Primary button | `#6366F1` | `#818CF8` |
| Borders | `#E2E8F0` | `#334155` |
| Shadows | Black at 5-10% | Black at 20-30% |

### 8.3 Dark Mode CSS

```scss
@media (prefers-color-scheme: dark)
  :root
    --bg-primary: #0F172A
    --bg-secondary: #1E293B
    --bg-tertiary: #334155
    --text-primary: #F8FAFC
    --text-secondary: #94A3B8
    --border-default: #334155

  img:not([src*=".svg"])
    filter: brightness(0.9)

  .illustration
    filter: brightness(0.95) contrast(1.05)
```

### 8.4 PWA Theme Colors

```json
{
  "theme_color": "#6366F1",
  "background_color": "#FFFFFF"
}
```

---

## 9. Motion and Animation

### 9.1 Timing Functions

| Name | Cubic Bezier | Usage |
|------|--------------|-------|
| `ease-out` | `cubic-bezier(0, 0, 0.2, 1)` | Enter animations |
| `ease-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exit animations |
| `ease-in-out` | `cubic-bezier(0.4, 0, 0.2, 1)` | Move, resize |
| `bounce` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful success states |

### 9.2 Duration Scale

| Token | Duration | Usage |
|-------|----------|-------|
| `--duration-instant` | 100ms | Hover, active states |
| `--duration-fast` | 150ms | Micro-interactions |
| `--duration-normal` | 200ms | Default transitions |
| `--duration-slow` | 300ms | Modals, drawers |
| `--duration-slower` | 500ms | Page transitions |

### 9.3 Animation Patterns

| Pattern | Enter | Exit |
|---------|-------|------|
| Fade | opacity 0→1 | opacity 1→0 |
| Scale | scale(0.95)→1 + fade | scale(1)→0.95 + fade |
| Slide up | translateY(8px)→0 + fade | 0→translateY(-8px) + fade |
| Slide from right | translateX(100%)→0 | 0→translateX(100%) |

### 9.4 Reduced Motion

```scss
@media (prefers-reduced-motion: reduce)
  *,
  *::before,
  *::after
    animation-duration: 0.01ms !important
    animation-iteration-count: 1 !important
    transition-duration: 0.01ms !important
    scroll-behavior: auto !important
```

---

## 10. Sync Status Visuals

### 10.1 OfflineBanner

```scss
.offline-banner
  position: fixed
  bottom: calc(56px + var(--safe-area-inset-bottom))
  left: 0
  right: 0
  padding: var(--space-3) var(--space-4)
  display: flex
  align-items: center
  gap: var(--space-3)
  font-size: var(--text-body-sm)
  z-index: 100

  &.offline
    background: var(--warning)
    color: var(--dark)

  &.syncing
    background: var(--info)
    color: white

  &.error
    background: var(--negative)
    color: white

  &.online
    background: var(--positive)
    color: white
    animation: slide-out-down 0.3s ease-in 2.7s forwards
```

### 10.2 SyncStatus Icon

```scss
.sync-status
  position: relative

  .sync-icon
    font-size: 24px
    color: var(--text-secondary)

    &.synced
      color: var(--positive)

    &.syncing
      animation: pulse 1.5s ease-in-out infinite

    &.error
      color: var(--negative)

  .sync-badge
    position: absolute
    top: -4px
    right: -4px
    min-width: 18px
    height: 18px
    border-radius: 9px
    background: var(--negative)
    color: white
    font-size: var(--text-overline)
    display: flex
    align-items: center
    justify-content: center

@keyframes pulse
  0%, 100%
    opacity: 1
  50%
    opacity: 0.5
```

---

## 11. Border Radius System

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 4px | Small elements, badges |
| `--radius-md` | 8px | Buttons, inputs, small cards |
| `--radius-lg` | 12px | Cards, dialogs |
| `--radius-xl` | 16px | Large modals, sheets |
| `--radius-full` | 9999px | Pills, avatars, circular buttons |

---

## 12. Shadow System

| Token | Value | Usage |
|-------|-------|-------|
| `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle elevation |
| `--shadow-sm` | `0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06)` | Cards default |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1), 0 2px 4px rgba(0,0,0,0.06)` | Cards hover |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1), 0 4px 6px rgba(0,0,0,0.05)` | Dropdowns, popovers |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04)` | Modals |

---

## 13. Quasar Configuration

```typescript
// /services/frontend/quasar.config.ts - framework.config.brand

brand: {
  primary: '#6366F1',      // Indigo 500
  secondary: '#14B8A6',    // Teal 500
  accent: '#FBBF24',       // Amber 400
  dark: '#0F172A',         // Slate 900
  positive: '#16A34A',     // Green 600 (WCAG AA)
  negative: '#DC2626',     // Red 600
  info: '#2563EB',         // Blue 600
  warning: '#D97706'       // Amber 600
}
```

---

## 14. Accessibility Checklist

| Requirement | Specification |
|-------------|---------------|
| Color contrast (text) | Minimum 4.5:1 for body text, 3:1 for large text |
| Color contrast (UI) | Minimum 3:1 for interactive elements |
| Focus indicators | 2px solid outline with 2px offset, primary color |
| Touch targets | Minimum 44x44px |
| Motion | Respect `prefers-reduced-motion` |
| Color independence | Never use color alone to convey meaning |
| Screen reader | All interactive elements have accessible names |

---

## 15. Implementation Priority

### Phase 1: Foundation (Before Launch)
- Color palette CSS variables
- Typography scale
- Spacing system
- Button and input component styles
- Card component styles
- Offline/sync status indicators
- Skeleton loading states

### Phase 2: Polish (V1.1)
- Empty state illustrations
- Micro-animations
- Dark mode implementation
- Custom icons for brand identity

### Phase 3: Enhancement (V1.2+)
- Advanced animation system
- Celebration animations (confetti for all-marked)
- Seasonal theme variations
- Custom illustration library
