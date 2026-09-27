---
name: DHM Group
description: Premium dark tech studio for web, mobile and business email, proven by apps it runs in production.
colors:
  brand: "#F05A2B"
  ink: "#000000"
  panel: "#181818"
  raised: "#1F1F1F"
  line: "#272727"
  scrollbar: "#313131"
  muted: "#A3A3A3"
  heading-fade: "#9B9B9B"
  white: "#FFFFFF"
typography:
  display:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "48px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "36px"
    fontWeight: 600
    lineHeight: "40px"
    letterSpacing: "-0.025em"
  title-lg:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: "36px"
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: "32px"
    letterSpacing: "-0.025em"
  title-sm:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: "28px"
  body-lg:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: "28px"
  body:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: "24px"
  button:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: "24px"
  label:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
  caption:
    fontFamily: "Geist, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
  data:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
rounded:
  lg: "8px"
  xl: "12px"
  2xl: "16px"
  3xl: "24px"
  4xl: "32px"
  full: "9999px"
spacing:
  "0": "0"
  "25": "2px"
  "50": "4px"
  "75": "8px"
  "100": "12px"
  "200": "16px"
  "300": "24px"
  "400": "32px"
  "500": "40px"
  "600": "48px"
  "700": "64px"
  "800": "80px"
  "900": "96px"
components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.ink}"
    typography: "{typography.button}"
    rounded: "{rounded.full}"
    padding: "8px 12px"
  button-primary-hover:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
  button-ghost:
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "8px 12px"
  field:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.white}"
    typography: "{typography.body}"
    rounded: "{rounded.xl}"
    padding: "12px 12px"
  chip-toggle:
    textColor: "{colors.white}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "8px 12px"
  chip-toggle-selected:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.ink}"
  card-panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.white}"
    rounded: "{rounded.2xl}"
    padding: "32px"
  faq-item:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.white}"
    typography: "{typography.body-lg}"
    rounded: "{rounded.2xl}"
    padding: "16px 24px"
  nav-pill:
    backgroundColor: "#00000099"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "8px 8px 8px 16px"
---

# Design System: DHM Group

## Overview

**Creative North Star: "The Live Build"**

A premium dark studio that shows running software instead of describing it. The ground is pure black; content sits on flat charcoal panels outlined by a single hairline; type is white Geist, set tight and semibold at the top of the hierarchy and quiet grey beneath. Orange is not decoration. It marks the one thing to press and the things that are live, and nothing else.

Density is calm and generous: one 1152px column, 96px between sections, 32px inside panels. Proof is carried by authored product surfaces (phone screens, a browser frame, mailbox rows) drawn in the same tokens as the page and captioned as illustrative. Motion is heavy and fluid: every state change and reveal eases on one spring curve at 700ms or longer, so the page feels weighty rather than twitchy.

The craft bar is Linear and Framer executed straight, with no themed metaphor. Backgrounds never carry gradients; the single gradient in the system lives inside the hero heading's letterforms.

**Key Characteristics:**
- Black ground, flat charcoal panels, 1px hairline outlines
- Orange reserved for action, selection, live status, focus and errors
- Geist only, with Geist Mono for data strings
- Tailwind type scale and a fixed 13 step spacing ladder
- Generous 16px panel corners, pill shaped controls, nested radii by formula
- One fluid easing curve for all motion

## Colors

A near monochrome dark ladder with one hot orange accent that is rationed to meaning.

### Primary
- **Signal Orange** (brand): the primary button fill, selected service chips, the live status dot, the active chip in authored app screens, inline error text and error outline, the focus ring, text selection and the input caret. On hover the primary button turns white rather than a deeper orange.

### Neutral
- **Studio Black** (ink): page ground, field backgrounds, device screen backgrounds, and the text colour on orange fills.
- **Charcoal Panel** (panel): every card, FAQ item, quote panel and device frame.
- **Raised Charcoal** (raised): elements that sit on a panel or inside a device screen: inactive chips, search bars, the URL bar, avatar discs.
- **Hairline** (line): 1px outlines on panels, fields, chips and ghost buttons; section and list dividers; inert browser dots.
- **Scroll Track Grey** (scrollbar): scrollbar thumb only.
- **Quiet Grey** (muted): secondary text, subheadings, body copy inside panels, nav links at rest, icons at rest.
- **Heading Fade** (heading-fade): end stop of the hero heading gradient only.
- **White** (white): primary text, headings, the primary button hover fill, and the translucent white overlays (10% current nav item, 5% ghost hover, 20 to 40% hover outlines).

### Named Rules
**The Action Orange Rule.** Orange appears only on the primary action, a selected or live state, focus, selection and errors. Never fill a panel, background, divider or decorative shape with it.

**The Flat Ground Rule.** Backgrounds come only from the dark ladder (#000000, #181818, #1F1F1F, #272727, #313131, #131209) and are always flat. The one gradient is the hero heading text, left to right from white to Heading Fade.

## Typography

**Display Font:** Geist (with ui-sans-serif, system-ui)
**Body Font:** Geist
**Label/Mono Font:** Geist Mono, for data only

**Character:** One neutral grotesk carries everything; hierarchy comes from size, semibold weight and tight tracking, not from a second face. Geist Mono appears only where the content is machine shaped: URLs, email addresses, phone numbers, prices.

### Hierarchy
- **Display** (600, 48px, line height 1, tight): the hero heading and the 404 heading, filled with the white to grey text gradient, capped at 680px with line breaks where the thought breaks. The tagline reveal steps from headline to display size at md.
- **Headline** (600, 36px / 40px, tight): section headings, capped at 680px.
- **Title Large** (600, 30px / 36px, tight): product names on the apps panels.
- **Title** (600, 24px / 32px, tight): service panel headings and confirmation headings.
- **Title Small** (600, 20px / 28px): process step headings.
- **Body Large** (400, 18px / 28px): section subheadings in Quiet Grey, FAQ questions at weight 500.
- **Body** (400, 16px / 24px): panel copy and FAQ answers, in Quiet Grey.
- **Button** (600, 16px / 24px): main buttons; header and ghost buttons drop to 14px.
- **Label** (500, 14px / 20px): form labels, list items, nav links, chips.
- **Caption** (400, 12px / 16px): illustrative captions, device status bars, metadata lines.
- **Data** (Geist Mono 500, 14px / 20px, 12px inside mockups): URLs, addresses, prices, phone numbers.

### Named Rules
**The One Face Rule.** Geist is the only typeface. Geist Mono is allowed only for data strings. No italics anywhere, and no weight above 700.

**The Scale Snap Rule.** Every size lands on a Tailwind scale step with its paired line height; tracking is tightened only on semibold headings. Headings use balanced wrapping, body copy uses pretty wrapping, so no word is ever orphaned.

## Layout

Single centred column at max 1152px (max-w-6xl) with 16px side gutters, 24px from sm. Sections are separated by 96px of vertical padding; heading to subheading is 24px, heading block to content grid is 64px. Grids use 16px gutters between panels and 32 to 64px between text columns.

Spacing resolves only to the ladder in the frontmatter (0, 2, 4, 8, 12, 16, 24, 32, 40, 48, 64, 80, 96px). Panel padding is 32px; the quote panel steps 24px, 40px, 64px across breakpoints.

Responsive behaviour: grids collapse to one column below md or lg; the services area becomes an asymmetric bento at lg (a two column wide panel, a single panel, a full width panel); the hero splits 1.5fr to 1fr at lg. The nav pill hides its links below md and swaps in the morphing menu button.

## Elevation & Depth

Depth is tonal, not shadowed. Layers step from Studio Black to Charcoal Panel to Raised Charcoal, and each panel is outlined by a 1px Hairline. Glass appears only on navigation: the floating pill (60% black, extra large backdrop blur, 10% white outline) and the full screen mobile menu (80% black, 3xl backdrop blur).

### Shadow Vocabulary
- **Device drop** (`box-shadow: 0 24px 64px rgb(0 0 0 / 0.6)`): under authored phone frames only, to lift them off the ground.

### Named Rules
**The Tonal Step Rule.** To raise a surface, step it one rung up the dark ladder and give it a hairline. Shadows are reserved for device mockups.

## Shapes

Soft, generous corners on containers and fully round controls. Panels and FAQ items use 16px corners; fields and small inset rows 12px; inner screens 8px; phone frames 32px with a 24px screen. Every button, chip, nav link and the nav itself is a full pill.

Borders go all the way around a card or not at all. Single side hairlines appear only as dividers between sections, list rows and the footer, never on a card.

**The Nested Radius Rule.** When a shape sits inside another with a gap under 32px, inner radius equals outer radius minus the gap, applied only when the result exceeds 2px (phone frame 32px with 8px padding gives a 24px screen; a 16px browser frame with 8px padding gives an 8px page).

## Components

### Buttons
Confident pills with a slow, weighty response.
- **Shape:** full pill (9999px), 8px by 12px padding, icon gap 8px.
- **Primary:** Signal Orange fill, black semibold text; one per viewport. A trailing arrow icon on main instances.
- **Hover / Focus:** fill turns white over 700ms on the fluid curve; press scales to 0.98; focus shows a 2px orange outline offset 2px.
- **Ghost:** transparent with a Hairline outline and white text at 14px; hover lifts the outline to 40% white and adds a 5% white wash. Unavailable links render at 50% opacity with pointer events off, never as dead links.
- **Loading:** label changes to a sending message and the fill pulses at 60% orange.

### Chips
- **Style:** service toggles are Hairline outlined pills, 14px white text, 8px by 12px padding.
- **State:** hover lifts the outline to 40% white; selected fills Signal Orange with black text; keyboard focus shows the orange outline.

### Cards / Containers
- **Corner Style:** 16px.
- **Background:** Charcoal Panel, with inset rows in Studio Black or Raised Charcoal.
- **Shadow Strategy:** none; see Elevation & Depth.
- **Border:** 1px Hairline on all sides; an emphasised inset row may use a 30% white outline.
- **Internal Padding:** 32px.

### Inputs / Fields
- **Style:** Studio Black fill, 1px Hairline outline, 12px corners, 12px padding, 16px text, orange caret. Labels sit 8px above in 14px medium.
- **Focus:** outline turns Signal Orange, no glow.
- **Hover:** outline lifts to 30% white.
- **Error:** outline forced to Signal Orange with a 14px orange message below; form level errors sit in a 12px rounded box with a 60% orange outline.
- **Disabled:** 50% opacity, not allowed cursor.

### Navigation
- **Style:** floating glass pill 24px from the top, centred at content width; logo at 32px height, links in 14px Quiet Grey with 8px by 12px pill hit areas, a 14px primary button at the end.
- **States:** hover turns links white; the current section gets a 10% white pill and white text.
- **Mobile:** a two bar button morphs into an X by rotating each bar 45 degrees; the menu opens as a full screen glass overlay with 36px semibold links that rise 48px and fade in, staggered 100, 150, 200ms and onward.

### FAQ Item
Charcoal Panel disclosure with a 16px corner and Hairline outline; the question is 18px medium with 16px by 24px padding, the answer Quiet Grey body. A plus icon rotates 45 degrees to a cross when open; hover lifts the outline to 20% white.

### Authored Product Screen
Signature proof device. Phone frames are Charcoal Panel at 32px corners with an 8px bezel and the device drop shadow; screens are Studio Black at 24px. Browser frames use a 16px Studio Black frame, three Hairline dots and a Raised Charcoal URL bar in Geist Mono. Content inside uses only system tokens (Raised Charcoal cards, Hairline dividers, one orange active chip). Every authored screen carries a right aligned 12px caption reading "Illustrative".

### Tagline Reveal
A large headline to display sized statement capped at 680px. Words start at 30% white and turn fully white one at a time as they cross a line 65% down the viewport (scroll listener throttled through requestAnimationFrame), 700ms on the fluid curve. Once the last word lights, the tagline artwork wipes in left to right over 1400ms. Reduced motion shows everything lit.

## Do's and Don'ts

### Do:
- **Do** ease every transition on cubic-bezier(0.32, 0.72, 0, 1) at 700ms; scroll reveals rise 64px from a 12px blur over 900ms, staggered in 120ms steps, via IntersectionObserver.
- **Do** keep content visible without JavaScript and under reduced motion; hide reveals only when both script and motion are available.
- **Do** raise surfaces by stepping the dark ladder and adding a 1px Hairline.
- **Do** ship hover, press (0.98 scale), orange focus ring, loading, error and disabled states on every control.
- **Do** caption every authored product screen as illustrative.
- **Do** use Phosphor icons (regular, and fill for platform logos) at text size alongside labels.
- **Do** apply the nested radius formula whenever a shape sits within 32px of its container's edge.

### Don't:
- **Don't** put a gradient on any background; the hero heading text is the only gradient.
- **Don't** use Signal Orange on panels, dividers or decoration.
- **Don't** use Inter, Roboto, Arial, Open Sans or Helvetica, any italic, or a weight above 700.
- **Don't** set Geist Mono on prose, headings or buttons.
- **Don't** use Material Icons or Material Symbols.
- **Don't** use default easing or unthrottled scroll listeners.
- **Don't** outline only one side of a card.
- **Don't** use spacing, font sizes or radii outside the frontmatter scales.
