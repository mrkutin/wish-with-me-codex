# Visual Design Refresh - Gift Theme

> Comprehensive design specification for adding gift-themed decorations and styling across all pages.
> Builds upon the existing design system in `docs/11-visual-design.md`.

---

## 1. Design Philosophy

### 1.1 Core Principles

| Principle | Description |
|-----------|-------------|
| **Light & Airy** | Plenty of whitespace, soft colors, minimal visual weight |
| **Gift-Forward** | Visual elements clearly communicate "gifts & wishlists" |
| **Consistent** | Same background and decorations across all pages |
| **Non-Intrusive** | Decorations enhance without interfering with content |
| **Performant** | SVG-based, CSS-driven, no heavy images |

### 1.2 Visual Identity Keywords

- Celebration
- Warmth
- Softness
- Ribbons & Bows
- Sparkles
- Gift boxes
- Pastel accents

---

## 2. Extended Color Palette

### 2.1 New Gift Accent Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Coral 50** | `#FFF1F2` | 255, 241, 242 | Warm backgrounds, gradient overlay |
| **Coral 100** | `#FFE4E6` | 255, 228, 230 | Hover accents |
| **Coral 400** | `#FB7185` | 251, 113, 133 | Ribbon accents, decorative elements |
| **Coral 500** | `#F43F5E` | 244, 63, 94 | Ribbon highlights, CTAs |
| **Gold 300** | `#FCD34D` | 252, 211, 77 | Sparkle accents |
| **Gold 400** | `#FBBF24` | 251, 191, 36 | Primary sparkles (existing accent) |
| **Peach 50** | `#FEF7ED` | 254, 247, 237 | Warm tint overlay |
| **Peach 100** | `#FFECD2` | 255, 236, 210 | Gradient warmth |

### 2.2 CSS Variables to Add

```scss
:root
  // Gift accent colors
  --gift-coral-50: #FFF1F2
  --gift-coral-100: #FFE4E6
  --gift-coral-400: #FB7185
  --gift-coral-500: #F43F5E
  --gift-gold-300: #FCD34D
  --gift-gold-400: #FBBF24
  --gift-peach-50: #FEF7ED
  --gift-peach-100: #FFECD2

  // Decoration opacity
  --decoration-opacity: 0.06
  --decoration-opacity-hover: 0.1

  // Background gradient
  --bg-gradient-start: #FFFFFF
  --bg-gradient-end: var(--gift-coral-50)
```

### 2.3 Dark Mode Adjustments

```scss
.body--dark
  --gift-coral-50: rgba(251, 113, 133, 0.05)
  --gift-coral-100: rgba(251, 113, 133, 0.08)
  --gift-coral-400: #FB7185
  --decoration-opacity: 0.03
  --decoration-opacity-hover: 0.06
  --bg-gradient-start: #0F172A
  --bg-gradient-end: rgba(251, 113, 133, 0.03)
```

---

## 3. Background System

### 3.1 Global Background

The background should be consistent across ALL pages, creating visual continuity.

```scss
// Applied to body or main layout wrapper
.app-background
  background:
    // Subtle gradient from white to warm coral tint
    linear-gradient(
      180deg,
      var(--bg-gradient-start) 0%,
      var(--bg-gradient-end) 100%
    )
  background-attachment: fixed  // Stays fixed while content scrolls
  min-height: 100vh
```

### 3.2 Decorative Pattern Layer

A subtle pattern of gift-themed SVG elements overlaid on the background.

```scss
.app-background::before
  content: ''
  position: fixed
  top: 0
  left: 0
  right: 0
  bottom: 0
  pointer-events: none
  z-index: 0
  opacity: var(--decoration-opacity)
  background-image: url('data:image/svg+xml,...')  // Inline SVG pattern
  background-size: 400px 400px
  background-repeat: repeat
```

### 3.3 Pattern Tile Content (400x400px)

The pattern tile should contain:
- 2-3 small gift boxes (different sizes, rotated)
- 4-5 sparkle/star shapes
- 1-2 ribbon curl elements
- 1 small bow

**Placement within tile (approximate coordinates):**
```
Gift box 1: (50, 80) - 32x32px, rotate(-15deg)
Gift box 2: (280, 200) - 24x24px, rotate(10deg)
Sparkle 1: (120, 40) - 16px
Sparkle 2: (320, 100) - 12px
Sparkle 3: (180, 280) - 14px
Sparkle 4: (60, 340) - 10px
Sparkle 5: (350, 320) - 16px
Ribbon curl: (220, 60) - 40x20px
Bow: (150, 180) - 28x20px, rotate(5deg)
```

---

## 4. SVG Decorative Elements

### 4.1 Gift Box Icon

```svg
<svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Box body -->
  <rect x="4" y="14" width="24" height="16" rx="2" fill="#FB7185" fill-opacity="0.3"/>
  <!-- Box lid -->
  <rect x="2" y="10" width="28" height="6" rx="1.5" fill="#FB7185" fill-opacity="0.4"/>
  <!-- Vertical ribbon -->
  <rect x="14" y="10" width="4" height="20" fill="#F43F5E" fill-opacity="0.5"/>
  <!-- Horizontal ribbon -->
  <rect x="2" y="12" width="28" height="3" fill="#F43F5E" fill-opacity="0.5"/>
</svg>
```

### 4.2 Sparkle/Star Icon

```svg
<svg viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M8 0L9.5 6.5L16 8L9.5 9.5L8 16L6.5 9.5L0 8L6.5 6.5L8 0Z" fill="#FBBF24" fill-opacity="0.6"/>
</svg>
```

### 4.3 Ribbon Curl

```svg
<svg viewBox="0 0 40 20" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M2 18C2 18 10 2 20 10C30 18 38 2 38 2" stroke="#FB7185" stroke-width="3" stroke-linecap="round" stroke-opacity="0.4"/>
</svg>
```

### 4.4 Bow Icon

```svg
<svg viewBox="0 0 28 20" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Left loop -->
  <ellipse cx="7" cy="10" rx="6" ry="8" fill="#FB7185" fill-opacity="0.35"/>
  <!-- Right loop -->
  <ellipse cx="21" cy="10" rx="6" ry="8" fill="#FB7185" fill-opacity="0.35"/>
  <!-- Center knot -->
  <circle cx="14" cy="10" r="3" fill="#F43F5E" fill-opacity="0.5"/>
  <!-- Tails -->
  <path d="M11 13L4 20M17 13L24 20" stroke="#F43F5E" stroke-width="2" stroke-linecap="round" stroke-opacity="0.4"/>
</svg>
```

---

## 5. Corner Decorations

Decorative elements in corners that frame content without obstructing it.

### 5.1 Top-Left Corner Ribbon

```scss
.corner-decoration-tl
  position: fixed
  top: 0
  left: 0
  width: 120px
  height: 120px
  pointer-events: none
  z-index: 1
  opacity: 0.08

  // SVG of ribbon bow coming from corner
```

### 5.2 Bottom-Right Corner Ribbon

```scss
.corner-decoration-br
  position: fixed
  bottom: 0
  right: 0
  width: 100px
  height: 100px
  pointer-events: none
  z-index: 1
  opacity: 0.08
  transform: rotate(180deg)
```

### 5.3 Corner Ribbon SVG (120x120)

```svg
<svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Ribbon coming from top-left corner -->
  <path d="M0 0L40 0C40 0 60 20 60 40C60 60 80 60 120 40"
        stroke="#FB7185" stroke-width="8" fill="none"/>
  <path d="M0 0L0 40C0 40 20 60 40 60C60 60 60 80 40 120"
        stroke="#FB7185" stroke-width="8" fill="none"/>
  <!-- Small bow at corner -->
  <ellipse cx="20" cy="20" rx="12" ry="8" fill="#FB7185" transform="rotate(-45 20 20)"/>
  <ellipse cx="20" cy="20" rx="8" ry="12" fill="#FB7185" transform="rotate(-45 20 20)"/>
  <circle cx="20" cy="20" r="4" fill="#F43F5E"/>
</svg>
```

---

## 6. Page-Specific Decorations

### 6.1 Auth Pages (Login/Register)

**Enhanced decorations for first impression:**

```scss
.auth-page
  // Centered radial gradient for warmth
  background:
    radial-gradient(
      ellipse 80% 60% at 50% 40%,
      var(--gift-peach-50) 0%,
      transparent 70%
    ),
    linear-gradient(180deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%)
  background-attachment: fixed

  // Floating decorative elements
  .auth-decorations
    position: absolute
    inset: 0
    overflow: hidden
    pointer-events: none

    .floating-gift
      position: absolute
      opacity: 0.1
      animation: float 6s ease-in-out infinite

    .floating-gift-1
      top: 10%
      left: 5%
      width: 60px
      animation-delay: 0s

    .floating-gift-2
      top: 60%
      right: 8%
      width: 48px
      animation-delay: 2s

    .floating-sparkle
      position: absolute
      opacity: 0.15
      animation: twinkle 3s ease-in-out infinite

    .floating-sparkle-1
      top: 20%
      right: 15%
      width: 24px

    .floating-sparkle-2
      bottom: 30%
      left: 10%
      width: 20px
      animation-delay: 1.5s

@keyframes float
  0%, 100%
    transform: translateY(0) rotate(-5deg)
  50%
    transform: translateY(-15px) rotate(5deg)

@keyframes twinkle
  0%, 100%
    opacity: 0.15
    transform: scale(1)
  50%
    opacity: 0.25
    transform: scale(1.1)
```

### 6.2 Wishlists List Page

**Subtle header decoration:**

```scss
.wishlists-page
  // Ribbon accent under page title
  .page-title::after
    content: ''
    display: block
    width: 60px
    height: 4px
    background: linear-gradient(90deg, var(--gift-coral-400), var(--gift-gold-400))
    border-radius: 2px
    margin-top: var(--space-2)
```

### 6.3 Wishlist Detail Page

**Gift-themed section headers:**

```scss
.wishlist-detail-page
  // Decorative bow icon next to wishlist title
  .wishlist-header
    position: relative

    &::before
      content: ''
      position: absolute
      left: -40px
      top: 50%
      transform: translateY(-50%)
      width: 28px
      height: 20px
      background: url('bow-icon.svg') no-repeat center
      opacity: 0.3
```

### 6.4 Shared Wishlist Page

**Special styling for public view:**

```scss
.shared-wishlist-page
  // Gradient banner at top
  .share-banner
    background: linear-gradient(
      135deg,
      var(--gift-coral-50) 0%,
      var(--gift-peach-50) 50%,
      var(--gift-coral-50) 100%
    )
    border-bottom: 2px solid var(--gift-coral-100)
    padding: var(--space-4)
    text-align: center

    .gift-icon
      color: var(--gift-coral-400)
      font-size: 24px
      margin-right: var(--space-2)
```

### 6.5 Profile & Settings Pages

**Minimal decorations:**

```scss
.profile-page,
.settings-page
  // Just the global background + subtle top gradient line
  .page-container::before
    content: ''
    position: absolute
    top: 0
    left: 0
    right: 0
    height: 3px
    background: linear-gradient(90deg,
      var(--gift-coral-400) 0%,
      var(--gift-gold-400) 50%,
      var(--gift-coral-400) 100%
    )
    opacity: 0.5
```

---

## 7. Component Enhancements

### 7.1 Card Styling

```scss
.wishlist-card,
.item-card
  position: relative
  overflow: hidden

  // Subtle shimmer on hover
  &::before
    content: ''
    position: absolute
    top: 0
    left: -100%
    width: 50%
    height: 100%
    background: linear-gradient(
      90deg,
      transparent,
      rgba(251, 191, 36, 0.05),
      transparent
    )
    transition: left 0.5s ease
    pointer-events: none

  &:hover::before
    left: 100%

  // Optional: ribbon tab on corner
  &.has-ribbon
    &::after
      content: ''
      position: absolute
      top: 0
      right: 0
      width: 0
      height: 0
      border-style: solid
      border-width: 0 32px 32px 0
      border-color: transparent var(--gift-coral-400) transparent transparent
      opacity: 0.15
```

### 7.2 Button Enhancements

```scss
// Primary buttons get subtle sparkle on hover
.q-btn--unelevated.bg-primary
  position: relative
  overflow: hidden

  &::after
    content: ''
    position: absolute
    top: 50%
    left: 50%
    width: 0
    height: 0
    background: radial-gradient(circle, rgba(255,255,255,0.3) 0%, transparent 70%)
    transform: translate(-50%, -50%)
    transition: width 0.3s, height 0.3s
    pointer-events: none

  &:hover::after
    width: 120%
    height: 120%
```

### 7.3 Empty State Enhancements

```scss
.empty-state
  position: relative

  // Floating gift decoration
  &::before
    content: ''
    position: absolute
    top: -20px
    right: 20%
    width: 40px
    height: 40px
    background: url('gift-outline.svg') no-repeat center
    opacity: 0.1
    animation: float 4s ease-in-out infinite

  // Sparkles around illustration
  .empty-illustration
    position: relative

    &::before,
    &::after
      content: ''
      position: absolute
      width: 16px
      height: 16px
      background: url('sparkle.svg') no-repeat center
      opacity: 0.2
      animation: twinkle 2s ease-in-out infinite

    &::before
      top: -10px
      right: -10px

    &::after
      bottom: -5px
      left: -10px
      animation-delay: 1s
```

---

## 8. Icon Set

### 8.1 Custom Gift Icons (Material Design style)

| Icon Name | Purpose | Description |
|-----------|---------|-------------|
| `gift-box` | Wishlist icon | Closed gift box with ribbon |
| `gift-open` | Empty wishlist | Open gift box |
| `gift-add` | Add item FAB | Gift box with + |
| `ribbon` | Decorative | Curled ribbon |
| `bow` | Decorative | Bow shape |
| `sparkle` | Celebration | 4-point star |
| `confetti` | Success state | Scattered dots |
| `gift-stack` | Multiple items | Stacked boxes |

### 8.2 Icon Style Guidelines

- **Stroke width**: 1.5px (consistent with MDI)
- **Corner radius**: 2px on boxes
- **Colors**: Use current color (inherit) for flexibility
- **Sizes**: 20px (inline), 24px (navigation), 32px (headers), 64px (empty states)

---

## 9. Animation Specifications

### 9.1 Floating Animation

```scss
@keyframes float
  0%, 100%
    transform: translateY(0px) rotate(-3deg)
  50%
    transform: translateY(-10px) rotate(3deg)
```

### 9.2 Twinkle Animation

```scss
@keyframes twinkle
  0%, 100%
    opacity: var(--decoration-opacity)
    transform: scale(1)
  50%
    opacity: calc(var(--decoration-opacity) * 1.5)
    transform: scale(1.1)
```

### 9.3 Shimmer (for cards/buttons)

```scss
@keyframes shimmer
  0%
    transform: translateX(-100%)
  100%
    transform: translateX(100%)
```

### 9.4 Reduced Motion

```scss
@media (prefers-reduced-motion: reduce)
  .floating-gift,
  .floating-sparkle,
  .empty-illustration::before,
  .empty-illustration::after
    animation: none

  .wishlist-card::before,
  .q-btn::after
    transition: none
```

---

## 10. Dark Mode Considerations

### 10.1 Decoration Adjustments

```scss
.body--dark
  // Reduce decoration visibility significantly
  .corner-decoration-tl,
  .corner-decoration-br
    opacity: 0.03

  .floating-gift
    opacity: 0.05

  .floating-sparkle
    opacity: 0.08

  // Warm the dark background slightly
  .app-background
    background:
      radial-gradient(
        ellipse 100% 80% at 50% 0%,
        rgba(251, 113, 133, 0.03) 0%,
        transparent 50%
      ),
      var(--bg-primary)

  // Adjust coral colors for dark backgrounds
  --gift-coral-400: #F87171  // Slightly lighter for visibility
```

### 10.2 Gold/Sparkle in Dark Mode

```scss
.body--dark
  .sparkle-icon,
  .floating-sparkle
    // Gold stands out well on dark - can be slightly brighter
    --gift-gold-400: #FCD34D
```

---

## 11. Implementation Files

### 11.1 New Files to Create

| File | Purpose |
|------|---------|
| `src/css/decorations.sass` | All decoration styles |
| `src/assets/icons/gift-box.svg` | Gift box icon |
| `src/assets/icons/gift-open.svg` | Open gift icon |
| `src/assets/icons/sparkle.svg` | Sparkle/star |
| `src/assets/icons/bow.svg` | Bow decoration |
| `src/assets/icons/ribbon-curl.svg` | Curled ribbon |
| `src/assets/patterns/gift-pattern.svg` | Background tile |
| `src/components/AppBackground.vue` | Background component |
| `src/components/CornerDecorations.vue` | Corner ribbon decorations |

### 11.2 Files to Modify

| File | Changes |
|------|---------|
| `src/css/app.sass` | Import decorations.sass, add CSS variables |
| `src/css/quasar.variables.sass` | Add gift accent colors |
| `src/layouts/MainLayout.vue` | Add AppBackground, CornerDecorations |
| `src/layouts/AuthLayout.vue` | Add floating decorations |
| `src/pages/LoginPage.vue` | Add auth-page class |
| `src/pages/RegisterPage.vue` | Add auth-page class |
| `src/pages/MyWishlistsPage.vue` | Add page-specific styles |
| `src/pages/WishlistPage.vue` | Add page-specific styles |
| `src/pages/SharedWishlistPage.vue` | Add share banner |
| `src/pages/ProfilePage.vue` | Add minimal decorations |
| `src/pages/SettingsPage.vue` | Add minimal decorations |

---

## 12. Accessibility

### 12.1 ARIA Requirements

```html
<!-- All decorative elements should be hidden from screen readers -->
<div class="corner-decoration-tl" aria-hidden="true"></div>
<div class="floating-gift" aria-hidden="true"></div>
<div class="app-background-pattern" aria-hidden="true" role="presentation"></div>
```

### 12.2 Motion Sensitivity

- All animations respect `prefers-reduced-motion`
- Decorations should never flash or pulse rapidly
- Animation durations are 3+ seconds for ambient motion

### 12.3 Color Independence

- Decorations are purely aesthetic - no information conveyed
- All functional elements remain high-contrast
- Gift theme expressed through shapes, not just colors

---

## 13. Performance Guidelines

### 13.1 SVG Optimization

- Inline SVGs for pattern (avoids HTTP requests)
- Simple paths, minimal nodes
- No filters or effects in pattern SVGs
- Use `will-change: transform` for animated elements

### 13.2 CSS Performance

```scss
// Use GPU-accelerated properties only
.floating-gift
  will-change: transform
  transform: translateZ(0)  // Force GPU layer

// Avoid animating expensive properties
// Good: transform, opacity
// Bad: width, height, top, left, box-shadow
```

### 13.3 Image Loading

- All decorative SVGs should be < 2KB each
- Pattern tile should be < 5KB total
- Use `loading="lazy"` for any image-based decorations

---

## 14. Implementation Priority

### Phase 1: Foundation
1. Add CSS variables for gift colors
2. Implement AppBackground component with gradient
3. Add background pattern SVG
4. Apply to MainLayout and AuthLayout

### Phase 2: Core Decorations
1. Create corner decoration SVGs
2. Implement CornerDecorations component
3. Add floating decorations to auth pages
4. Style page titles with ribbon underlines

### Phase 3: Component Polish
1. Add card shimmer effects
2. Button sparkle on hover
3. Empty state decorations
4. Custom gift icons

### Phase 4: Page-Specific
1. Shared wishlist banner
2. Profile/settings top gradient line
3. Wishlist detail bow decoration

---

## 15. Visual Reference Sketches

### 15.1 Overall Page Layout

```
┌─────────────────────────────────────────────────────┐
│ ╭─╮ Corner                                          │
│ ╰─╯ Ribbon         [Navbar]                         │
│                                                     │
│    ┌─────────────────────────────────────────┐     │
│    │                                         │     │
│    │              Page Content               │     │
│    │                                         │ ✧   │
│    │     ┌─────────┐     ┌─────────┐        │     │
│ 🎁 │     │  Card   │     │  Card   │        │ ✧   │
│    │     └─────────┘     └─────────┘        │     │
│    │                                         │     │
│    └─────────────────────────────────────────┘     │
│ ✧                                                   │
│                              ╭─╮ Corner             │
│         [Bottom Nav]         ╰─╯ Ribbon             │
└─────────────────────────────────────────────────────┘

Background: Subtle gradient (white → coral tint)
Pattern: Faint gift boxes + sparkles (6% opacity)
```

### 15.2 Auth Page Layout

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│        🎁                              ✧           │
│             ✧                                       │
│                    ┌───────────────┐                │
│                    │               │                │
│    ✧               │  Login Form   │      🎁       │
│                    │               │                │
│                    └───────────────┘                │
│  🎁                                          ✧     │
│                    ✧                                │
│                                                     │
└─────────────────────────────────────────────────────┘

Floating gifts: 10% opacity, slow float animation
Sparkles: 15% opacity, gentle twinkle
Center: Radial warm gradient glow
```

---

## 16. Approval Checklist

Before implementation, confirm:

- [ ] Color palette approved
- [ ] Background gradient intensity acceptable
- [ ] Pattern density and opacity reviewed
- [ ] Corner decoration visibility appropriate
- [ ] Auth page floating elements approved
- [ ] Animation speeds feel right
- [ ] Dark mode adjustments verified
- [ ] Performance impact acceptable
