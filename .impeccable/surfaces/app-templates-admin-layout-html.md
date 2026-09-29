---
version: 1
slug: "app-templates-admin-layout-html"
primary_target: "app/templates/admin/layout.html"
related_targets: ["app/templates/admin"]
---

# Surface: admin dashboard (app/templates/admin/)

Mode: Operate. Audience: 1–3 DHM staff; phone-first for inbox triage between meetings, laptop for content edits. Outcome: no lead goes unanswered; any lead's stage and history is readable at a glance; site content changes without a developer. Core flow under 30 s on a phone: open inbox, see unread count, open lead, Reply by email (mailto), move to Contacted with a note.

Round history: shape interview (phone-first inbox; pipeline with timeline; "same studio, quieter"), surface concept seed fd05883b dealt Ledger / Pipeline Board / Site Mirror; user locked **The Ledger** (code-led, no comp).

## Direction: The Ledger

- Visual authority: DESIGN.md unchanged. Quieter than the public site: no reveals, no gradients, no display type (largest is title 24px), transitions 150–250 ms, no new colours.
- Orange only for: primary action, selected tab/nav item, unread dot, focus, errors. Pipeline stages are neutral charcoal chips with text + icon.
- Shell: nav rail (labelled ≥1024px, icon rail 640–1023px, bottom tab bar <640px). Every section: header (title, count, primary action) → filter tabs + search → dense hairline list → record panel on the right (≥1024px) or full-screen record route (<1024px); records have their own URLs (`/admin/inquiries/42`).
- Focal moment: the lead record: contact, service chips, message, stage control (New / Contacted / Quoted / Won / Lost), Reply by email + Archive, activity timeline with note composer.

## Scope

Screens: sign-in, overview (unread + needs-action leads), inquiries list and record, legal (list, Markdown editor with side-by-side live preview), projects (list with up/down reorder, edit), site settings (incl. asset slots), asset library. Public site untouched. Anti-goals: charts/KPI tiles, drag-and-drop, WYSIWYG, roles, modals except destructive confirmation (`<dialog>`).

## States and ranges

Inquiries: up to a few hundred per year, 50 per page. Legal 2–6 pages; projects 2–10; assets up to ~200, ≤10 MB each. Empty states that teach; "Not notified" flag + Resend; upload progress; delete blocked with the referencing places named; sign-in wrong-password and lockout messages.

## Interaction

htmx swaps the record panel and pushes its URL; stage change saves inline and appends a system timeline entry; notes append optimistically; Markdown preview refreshes after 400 ms idle; publish is a switch; projects reorder with up/down buttons; success toasts (aria-live, auto-dismiss); errors inline; focus moves to swapped-in content.

## Constraints

htmx 4 (no implicit inheritance: CSRF via `hx-headers:inherited` on `<body>`); Tailwind tokens only; reuse `btn`, `field`; admin components as Jinja macros. Reply-by-email subject: "Re: Your quote request – DHM Group".
