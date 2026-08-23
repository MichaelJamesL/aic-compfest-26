# Visual language

Extracted from [`../ref/ui-ref.jpg`](../ref/ui-ref.jpg). Every colour below was
**sampled from that file** with a dominant-colour read over the named region —
they are the reference's actual values, not an approximation of its mood.

Read this before writing any UI code. It is not a suggestion.

---

## 1. What the reference actually is

A **dark navigation rail** runs down the left edge, full height and full bleed.
The rest is a **light work surface**, inset 12px and rounded. On that light
surface sit cards — most white, some in muted earth tones.

> **Two deliberate deviations from the reference.**
>
> 1. **Full bleed.** `ui-ref.jpg` frames its shell as a floating card on a
>    light-grey page — a marketing mockup's device framing, not an application
>    layout. The rail reaches every edge and casts no shadow.
> 2. **Inverted.** The reference puts white chrome around a dark canvas; ours is
>    the other way round. The rail is the constant furniture and recedes; the
>    work — long, text-heavy, read for minutes at a time — sits on light.
>
> Everything else below is taken from the reference unchanged: the palette, the
> card rhythm, the type scale, the restraint about colour.

The tokens are named by **role**, not by colour: `--surface*` and `--content*`
for the work surface, `--rail*` for the navigation. Inverting the two again is
an edit to those values, not a sweep through every component.

Four structural ideas carry the whole design. Copy these, not the invoice data:

1. **Two-tone shell.** Light chrome (navigation, brand, account) wraps a dark
   canvas (the work). Where you are stays light; what you are looking at is
   dark. Our app does the same: the rail and the account chrome are white, every
   analysis surface is black.
2. **Colour is scarce and earthy.** Black, white, grey — then exactly four muted
   tones: sage, apricot, clay, mint. No blue, no purple, no gradient. A card
   gets **one** colour, and colour marks a category, never decoration.
3. **The number is the design.** Metric cards are 80% empty space around one
   large tabular number. Titles are small and quiet; the value is loud.
4. **Depth comes from fill, not effects.** There are no shadows on any surface
   — light or dark. Surfaces separate by getting one step lighter
   (`#000` → `#111` → `#1E1E1E`) plus a hairline, and by the 12px inset that
   floats the black panel inside the white chrome.

What **not** to copy: the sample data, the "Upgrade to PREMIUM" card, the
donut-with-social-networks. Take the system, not the content.

---

## 1b. Brand

**Siena** — *Intelligence, grounded in industry.*

The name reads as the chain the product runs: **S**ense, **I**ntelligence,
**E**fficiency, **N**avigate, **A**ssist. That expansion is storytelling for the
proposal and the video; it does not belong in the UI.

| Asset | File | Surface |
| --- | --- | --- |
| Lockup, light | `public/logo-text-white.png` | the rail and any dark surface |
| Mark, light | `public/logo-white.png` | the collapsed 64px rail |
| Lockup, dark | `public/logo-text.png` | light surfaces — exports, print, slides |
| Mark, dark | `public/logo.png` | light surfaces; the source for the favicons |
| Favicons | `public/favicon-32.png`, `apple-touch-icon.png`, `icon-512.png` | generated: the dark mark on a light plate, so it survives a dark tab bar too |

### Pick the variant by measurement, not by eye

Both gradients were measured against `--rail` `#111111`:

| | darkest opaque pixel | vs rail |
| --- | --- | ---: |
| dark lockup | `#111614` | **1.03:1** |
| light lockup | `#769F8B` | **6.39:1** |

At 1.03:1 the last letters of the dark lockup vanish — "SIENA" renders as
"SIE". The light variants clear 4.5:1 across their whole gradient, so on the
rail they sit directly on the background with nothing behind them. An earlier
build put the dark lockup on a light plate; the plate is gone now that the
right file exists.

Never recolour, filter, or invert a variant to make it fit a surface. Pick the
one drawn for that surface, and if neither fits, measure before shipping.

### Rules

- The lockup appears **once**, at the top of the rail. Never repeat it in the
  header — the page title lives there.
- Light variants on dark surfaces, dark variants on light ones. There is no
  third option.
- The tagline appears once, under the lockup, on the wide rail only.
- Never place the mark on any accent tint. Both variants were measured against
  white and against the rail; nothing else is verified.
- The mark is never recoloured, rotated, or given effects.

## 2. Palette

### Neutrals — sampled

| Token | Value | Sampled from | Use |
| --- | --- | --- | --- |
**The work surface (light).**

| Token | Value | Use |
| --- | --- | --- |
| `--surface` | `#E5E5E5` | the panel base |
| `--surface-card` | `#FFFFFF` | cards |
| `--surface-raised` | `#F1F1F1` | icon chips, inputs, hover |
| `--content` | `#111111` | primary text |
| `--content-2` | `#5C5C5C` | labels, secondary rows |
| `--content-3` | `#616161` | captions, timestamps |
| `--line` | `rgba(17,17,17,.10)` | 1px separation |
| `--line-strong` | `rgba(17,17,17,.22)` | button borders, drop zones |

**The navigation rail (dark).**

| Token | Value | Use |
| --- | --- | --- |
| `--rail` | `#111111` | the rail, and the frame around the panel |
| `--rail-raised` | `#1E1E1E` | hover, chips |
| `--rail-content` | `#FFFFFF` | brand, active item |
| `--rail-content-2` | `#9A9A9A` | inactive item |
| `--rail-content-3` | `#7C7C7C` | inactive icon |
| `--rail-line` | `rgba(255,255,255,.10)` | 1px separation on the rail |

`--card` `#111111` is kept: the tinted accent cards set their text with it.

`--content-3` is `#616161`, not `#767676`. It appears on both the `#E5E5E5`
panel base and on white cards, and the lighter value clears 4.5:1 only on the
card — it measured **3.61:1** on the panel. Calibrate a token against the
darkest surface it lands on.

### Text

| Token | On dark | On light | Contrast | Use |
| --- | --- | --- | --- | --- |
| `--text-1` | `#FFFFFF` | `#111111` | 18.9:1 / 18.9:1 | values, names, headings |
| `--text-2` | `#9A9A9A` | `#5C5C5C` | 6.7:1 / 6.7:1 | labels, table headers, secondary rows |
| `--text-3` | `#7C7C7C` | `#767676` | 4.5:1 / 4.5:1 | captions, timestamps — the floor, never go lighter |

All three pass WCAG AA at 14px on every surface they appear on. There is no
fourth, dimmer step; if text needs to be quieter than `--text-3`, it needs to be
smaller or removed.

### Secondary text on a tinted card — use `text-soft`, never `--ink-dim`

`--ink-dim` is calibrated against white. On the four accent tints it collapses:

| Surface | `--ink-dim` (#5C5C5C) | `text-soft` (ink at 80%) |
| --- | --- | --- |
| `--sage` | **2.28:1** ✗ | 4.8:1 ✓ |
| `--clay` | **2.69:1** ✗ | 5.2:1 ✓ |
| `--mint` | **4.07:1** ✗ | 6.4:1 ✓ |
| `--apricot` | fails | passes |

So a tinted card never names a text colour. It inherits `#111111` from `Card`
and mutes with the `text-soft` utility — 80% opacity, measured, not guessed.
An earlier 65% was tried and measures 3.89:1 on clay.

These numbers come from `scripts/browser-pass.mjs`, which computes contrast
from what actually rendered — including opacity, blended rather than skipped.
Run it rather than reasoning about the palette table.

### Accents — sampled

| Token | Value | Sampled from |
| --- | --- | --- |
| `--sage` | `#7F9E8C` | the green card |
| `--apricot` | `#DD9251` | the weekly-report card |
| `--clay` | `#B4A193` | the sales-history card |
| `--mint` | `#B7D0BD` | the promo card |
| `--teal` | `#5F8B8A` | donut segment |
| `--burnt` | `#D26E3D` | donut segment |

Four card tones (`sage`, `apricot`, `clay`, `mint`) and two chart tones
(`teal`, `burnt`). That is the entire palette. Adding a colour is a design
decision, not an implementation detail — do not introduce one to make a state
"pop".

### Semantic mapping — our domain

Maintenance needs a severity ramp. Build it out of the sampled family instead of
importing a stoplight palette, so the product still looks like the reference:

| Meaning | Token | Value | Where |
| --- | --- | --- | --- |
| healthy / resolved / approved | `--ok` | `#7F9E8C` (sage) | health ≥ 80, verdict `resolved`, approved state |
| watch / medium priority | `--warn` | `#B4A193` (clay) | health 60–79, priority `medium` |
| high priority / degraded | `--high` | `#DD9251` (apricot) | health 40–59, priority `high`, `partial` verdict |
| critical / blocked / rejected | `--crit` | `#D26E3D` (burnt) | health < 40, priority `critical`, blockers, `not_resolved` |
| deterministic-value marker | `--teal` | `#5F8B8A` | numbers the engine computed, never the LLM |
| unavailable / not provided | `--text-3` | `#7C7C7C` | missing input in a partial-input run |

Four severity steps, monotonically warmer. `--crit` is a burnt orange, not red —
it is still distinguishable from `--high` at a glance, and it keeps the palette
intact. Never pair a severity colour with an emoji or an exclamation mark; the
colour and the number are the signal.

**Colour is never the only channel.** Every severity also carries a label
(`Kritis`, `Tinggi`, …) and, in charts, a distinct position or shape.

### Fills on dark

Coloured **text** on `#111111` needs a lighter tint than the card version.
Tints for pills and labels:

```
--ok-fill:   rgba(127,158,140,.24)   --ok-text:   #33564A
--warn-fill: rgba(180,161,147,.30)   --warn-text: #55443A
--high-fill: rgba(221,146,81,.28)    --high-text: #6D3F10
--crit-fill: rgba(210,110,61,.24)    --crit-text: #7D340F
--crit:      #D26E3D  (solid)        text: #111111
```

These are the light-surface values. The previous set was light-on-dark and is
unreadable here — a tint is calibrated for one surface, never both.

Note the asymmetry, taken straight from the reference: the negative badge is a
**solid** orange with dark text while the positive one is a soft tint. Bad news
is louder. Keep that.

---

## 3. Typography

**Plus Jakarta Sans** — geometric, high x-height, excellent numerals, and it
matches the reference's letterforms. It is also an Indonesian typeface, which
this product happens to be.

```css
font-family: 'Plus Jakarta Sans', ui-sans-serif, system-ui, -apple-system,
             'Segoe UI', Roboto, sans-serif;
```

Load weights 400/500/600 only. Never 700+ — the reference has no bold anywhere.

| Role | Size / line-height | Weight | Tracking | Notes |
| --- | --- | --- | --- | --- |
| Metric value | 30 / 34 | 600 | −0.02em | `tabular-nums`; the only large text on a card |
| Page title | 22 / 28 | 600 | −0.015em | "Selamat datang, …" |
| Section title | 17 / 24 | 600 | −0.01em | panel headings |
| Card title | 14 / 20 | 500 | 0 | sentence case |
| Body | 14 / 22 | 400 | 0 | |
| Table cell | 13 / 18 | 400 | 0 | `tabular-nums` on numbers |
| Table header | 12 / 16 | 500 | 0 | **sentence case**, `--text-3` |
| Caption / meta | 12 / 16 | 400 | 0 | `--text-3` |
| Badge | 11.5 / 14 | 500 | 0 | |

Rules:

- **Sentence case everywhere.** The reference's own table headers read
  "Customer ID", "Order Date" — not "CUSTOMER ID".
- **No uppercase letterspaced micro-labels.** Not for section labels, not for
  eyebrow text, not for table headers, not for badges. This is the single most
  common tell of generated UI and it appears nowhere in the reference.
- **Tabular numerals** on every metric, table column, timestamp and currency:
  `font-variant-numeric: tabular-nums`.
- One 600-weight element per card, maximum.
- Currency: `Rp 1.200.000` — Indonesian formatting, non-breaking space after
  `Rp`.

---

## 4. Space, size, radius

4px base unit. Allowed values: `4 8 12 16 20 24 32 40 56 72`. Nothing else.

| Thing | Value |
| --- | --- |
| Shell padding | 0 — the white chrome is full-bleed |
| Panel inset | 12 (the black panel floats inside the white shell) |
| Nav rail width | 232 |
| Nav rail padding | 20 |
| Panel padding | 16 |
| Card padding | 20 (16 below 640px) |
| Gap between cards | 12 |
| Gap between sections | 16 |
| Row height (table) | 44 |
| Nav item height | 40 |
| Control height (button, input) | 40; small 32 |
| Icon | 18 in nav and buttons, 16 inside chips |
| Icon chip | 36 circle |

Radii — the reference is generous and consistent:

| Token | Value | Applies to |
| --- | --- | --- |
| `--r-shell` | 28 | reserved; the shell is full-bleed and unrounded |
| `--r-panel` | 24 | the black work surface |
| `--r-card` | 20 | every card |
| `--r-control` | 12 | buttons, inputs, nav items, small tiles |
| `--r-pill` | 999 | badges, search field, avatars, icon chips |

Never nest two radii closer than 8px apart — an 20px card containing a 16px
inner box looks like a mistake. Card 20 → inner 12 is correct.

---

## 5. Depth

| Layer | Rail (dark) | Work surface (light) |
| --- | --- | --- |
| Base | `--rail` (fills the window) | `--surface` (inset 12) |
| Container | — | `--surface-card` + `--line` |
| Raised | `--rail-raised` | `--surface-raised` + `--line` |
| Floating | glass (§6) | glass (§6) |

```css
--shadow-float: 0 16px 40px -12px rgba(0,0,0,.55);
```

**There is exactly one shadow in this product**, and it belongs to floating
layers only. Cards get none — on dark they separate by fill step, on light by a
hairline. A shadow on a card is a bug. The shell used to cast a second one onto
a page gutter; the full-bleed layout removed both.

Focus: `outline: 2px solid` in `--text-1` with `outline-offset: 2px`. Visible
on both surfaces, never removed, never replaced with a colour glow.

---

## 6. Glass — restricted

Apple-style translucency, used the way Apple actually uses it: only on layers
that **float over moving content**. The reference contains exactly one such
element (the white chart tooltip), which is the right proportion.

Permitted on: the sticky top bar once the results page scrolls, popovers and
dropdowns, the modal surface and its scrim, chart tooltips, toasts.

```css
.glass-dark {
  background: rgba(17,17,17,.72);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,.10);
  box-shadow: var(--shadow-float);
}
/* Higher opacity than the dark variant: a light panel floating over a light
   surface has little to separate it, and .72 let body text bleed through the
   approval bar. */
.glass-light {
  background: rgba(255,255,255,.88);
  backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(17,17,17,.14);
  box-shadow: 0 12px 32px -10px rgba(17,17,17,.22);
}
@supports not (backdrop-filter: blur(1px)) {
  .glass-dark  { background: #141414; }
  .glass-light { background: #FFFFFF; }
}
```

Rules, in order of how often they are broken:

1. **Never on a static content card.** A card that does not float over anything
   gains nothing from blur and loses contrast. This is the failure mode that
   makes an interface look generated.
2. **Never nest glass inside glass.** A dropdown inside a glass header is opaque.
3. **Always ship the opaque fallback.** Text over a translucent layer with no
   blur support is unreadable.
4. **One hairline, no shadow stacking.** Glass already has a shadow; do not add
   a border *and* a ring *and* a glow.
5. Content behind glass must be real — if the backdrop is a flat colour, use
   the flat colour.

---

## 7. Components

### Nav rail
Dark (`--rail`), 232 wide, unrounded, full bleed. **Sticky and full height** —
`sticky top-0 h-screen overflow-y-auto` — so a long results page never scrolls
the navigation away. Below 1024 it collapses to a 64px icon strip; it is never
removed, and each item keeps an accessible name via `title` once its label is
hidden.

Brand at the top: a 20px mark plus the product name at 15/600.
Items are 40 tall, radius `--r-control`, 12px gap between icon and label,
14/500. Active: background `--rail-content`, label and icon `--rail`.
Inactive: label `--rail-content-2`, icon `--rail-content-3`, hover
`rgba(255,255,255,.05)`.

### Card
`--card` fill, radius `--r-card`, padding 20, no shadow. Optional hairline —
use it only where cards touch other cards. A coloured card (`--sage`,
`--apricot`, `--clay`, `--mint`) uses `#111111` for all its text; never white
text on these tones.

### Metric card
Row 1: 36px circular chip (`--raised`) with a 16px icon, then the title at
14/500, then an optional 28px circular action button on the far right with a
hairline border.
Row 2: the value at 30/600 tabular, 20px above.
Row 3: caption at 12 `--text-3` on the left, badge on the right.
Nothing else goes in a metric card. No sparkline, no progress bar, no
description.

### Badge / pill
Height 22, padding 0 8, radius `--r-pill`, 11.5/500. Tints from §2. Content is a
number with a sign, or one word. Never an icon plus a word plus a number.

### Button
Height 40, padding 0 18, radius `--r-control`, 14/500.
Primary on dark: `#FFFFFF` background, `#111111` text.
Primary on light: `#111111` background, `#FFFFFF` text.
Secondary: transparent with a hairline border, `--text-1`.
Ghost: text only, `--text-2`, hover `--text-1`.
Destructive: `--crit` background, `#111111` text — approval rejection only.
One primary button per screen region.

### Navigation must look like navigation

Hover is not an affordance. It does not exist on a touch screen, it does not
appear in a screenshot, and it does not help anyone deciding whether something
is clickable *before* they move the mouse. Anything that goes somewhere shows it
at rest.

| Going somewhere | Use | Renders |
| --- | --- | --- |
| A primary or secondary action | `LinkButton` | one `<a>` with the button treatment |
| Back up a level | `BackLink` | 32-tall pill, hairline border, hover surface |
| Inline in running text | `TextLink` | `--content`, **underlined at rest** |
| A table row | `Tr to=…` + `NavCell` + `ChevronCell` | row hover surface, underlined title, trailing chevron |

Rules:

- **Never wrap a `<Button>` in a `<Link>`.** That nests interactive content:
  two focus stops, ambiguous role, and invalid HTML. `LinkButton` renders one
  anchor and shares `controlClass` with `Button`, so the two cannot drift.
- **Never use `<Button onClick={() => navigate(…)}>`.** It looks like a button
  but is a navigation, so right-click, middle-click and open-in-new-tab all
  fail on it.
- A navigable row gets **three** signals — hover surface, underlined title,
  trailing chevron — because the first is invisible at rest and the third alone
  is easy to miss. The chevron is `tabIndex={-1}`: it goes where the title goes,
  and one destination should not cost two tab stops.
- `underline-offset-[3px]` with `decoration-line-strong`, darkening to
  `decoration-content` on hover. Never a coloured link: the palette has no link
  blue and is not getting one.

### Input
Height 40, `--card` on dark / `--shell` with hairline-ink on light, radius
`--r-control` (search fields use `--r-pill`, as in the reference), 14/400,
placeholder `--text-3`, 16px leading icon optional.
Labels sit above the field at 13/500 in `--text-2` — **not** floating, not
uppercase, not inside the field.

### Table
Header: 12/500 `--text-3`, sentence case, no background, no uppercase.
Rows: 44 tall, divider `1px solid var(--hairline)` between rows only — no
outer border, no zebra striping.
First cell `--text-3`, primary cell `--text-1` at 13.5/500, everything else
`--text-2`. Numbers right-aligned and tabular.
Status cell: a 6px dot in the severity colour plus the label — not a filled
chip, which fights the badges.

### Chart tooltip
The one glass element. `.glass-light` on dark charts, radius `--r-control`,
padding 8 12, value at 14/600 tabular, label at 11.5/400.

### Charts
- **Donut**: 150 diameter, 26 stroke, 2px gap between segments, rounded caps
  off. Centre holds one number at 30/600 plus a 12px caption. Segment colours
  from the accent list in fixed order — never a generated ramp.
- **Bars**: 14 wide, 10 gap, radius 6 on the top corners only, single colour
  with the highlighted bar one step darker. Baseline `--raised`, no gridlines
  above the axis, axis labels 11.5 `--text-3`.
- **Time series**: 1.5px stroke, no area fill, no point markers except on hover,
  no smoothing that invents data between samples.

Never: 3D, rainbow ramps, shadows on marks, animated draw-in longer than 300ms,
a legend where direct labels fit.

---

## 8. Motion

| Interaction | Duration | Easing |
| --- | --- | --- |
| Hover, press | 120ms | `ease-out` |
| Enter, expand | 240ms | `cubic-bezier(.2,.8,.2,1)` |
| Page transition | 200ms | fade + 4px rise, nothing more |

No bounce, no spring overshoot, no parallax, no scroll-linked animation, no
staggered card reveal. Honour `prefers-reduced-motion: reduce` by dropping to
opacity-only.

---

## 9. Banned — these make it look generated

Concrete, checkable, non-negotiable:

- Purple/blue/indigo anything. Gradient text, gradient buttons, gradient
  borders, gradient icon tiles.
- Glow, neon, `box-shadow` in an accent colour, coloured focus rings.
- Uppercase letterspaced micro-labels used as titles, eyebrows, or table
  headers.
- Emoji as icons or bullets, in the UI or in generated copy.
- Decorative background blobs, mesh gradients, noise textures, floating orbs,
  grid overlays, animated aurora.
- Glassmorphism on static cards (see §6.1).
- Border + shadow + gradient on the same element.
- More than one accent colour inside a single card.
- Rounded-square gradient tiles behind icons.
- `rotate-3`, perspective tilts, "3D" card hovers.
- Full-width centred hero with a giant headline — this is a tool, not a landing
  page.
- Skeletons that shimmer in a different hue than the surface.
- Placeholder or lorem content in anything that gets recorded.
- A dark/light theme toggle. The two-tone shell **is** the theme; a toggle is
  scope we did not agree to.

---

## 10. Tokens — paste into `src/index.css`

Tailwind v4, CSS-first configuration.

```css
@import "tailwindcss";

@theme {
  --color-page:      #E5E5E5;
  --color-shell:     #FFFFFF;
  --color-panel:     #000000;
  --color-card:      #111111;
  --color-raised:    #1E1E1E;

  --color-text-1:    #FFFFFF;
  --color-text-2:    #9A9A9A;
  --color-text-3:    #7C7C7C;
  --color-ink-1:     #111111;
  --color-ink-2:     #5C5C5C;
  --color-ink-3:     #767676;

  --color-sage:      #7F9E8C;
  --color-apricot:   #DD9251;
  --color-clay:      #B4A193;
  --color-mint:      #B7D0BD;
  --color-teal:      #5F8B8A;
  --color-burnt:     #D26E3D;

  --color-ok:        #7F9E8C;
  --color-warn:      #B4A193;
  --color-high:      #DD9251;
  --color-crit:      #D26E3D;

  --radius-shell:    28px;
  --radius-panel:    24px;
  --radius-card:     20px;
  --radius-control:  12px;

  --font-sans: 'Plus Jakarta Sans', ui-sans-serif, system-ui, -apple-system,
               'Segoe UI', Roboto, sans-serif;

  --shadow-shell: 0 24px 64px -24px rgba(17,17,17,.20),
                  0 2px 8px -2px rgba(17,17,17,.06);
  --shadow-float: 0 16px 40px -12px rgba(0,0,0,.55);
}

:root { --hairline: rgba(255,255,255,.08); --hairline-ink: rgba(17,17,17,.08); }

body { background: var(--color-shell); color: var(--color-ink-1);
       font-family: var(--font-sans); -webkit-font-smoothing: antialiased; }

.tnum { font-variant-numeric: tabular-nums; }
```

Font, self-hosted or from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet">
```

---

## 11. Self-check before committing UI

1. Does every colour on screen appear in §2? If not, delete it.
2. Is there any uppercase letterspaced text? Remove it.
3. Do any cards have shadows? Remove them. The only shadow is `--shadow-float`.
4. Is glass on anything that does not float? Make it opaque.
5. Is every number tabular?
6. Is there more than one primary button in view?
7. Do all spacing values come from the allowed set?
8. Does every severity read correctly in greyscale?
8b. Has `browser-pass` been run against the **production bundle**, not just the
    dev server? They are not the same CSS.
8c. Does every token still pass contrast on the *darkest* surface it appears on,
    not just the lightest?
9. Is any state (empty, loading, error, partial input) unstyled?
10. Would this screenshot be indistinguishable from a hundred other AI-built
    dashboards? If yes, the reference was not followed.
