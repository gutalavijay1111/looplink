# LoopLink Engineering Exercise — Campaign Builder & Distribution

**Role:** Senior Engineer (SDE 3), Fullstack
**Timebox:** ~3–4 hours of focused work (you have 24 hours from receipt to submit)

---

## 1. Context

LoopLink lets retailers and brands run **campaigns** — bundles of offers that go live for a window of time. A retailer or brand builds a campaign and launches it from an internal portal. Out in the world, a shopper discovers it (e.g. a QR code at the till), enrolls, and sees what they get.

You'll build a small slice of both halves:

- an internal **Campaign Builder** to create, edit, and run campaigns, and
- a public, mobile-friendly **enrollment page** a shopper reaches by scanning/opening a campaign's QR, where they identify themselves and see the offer.

Assume **a single team in one workspace — no multi-tenancy, no login**. The shopper-facing flow is deliberately **auth-free**: a shopper claims an identity, they don't create an account.

We care about how you own a feature across every layer — data model, API, two different UIs, the states, and the seams between them.

> Sandbox exercise. We will **not** ship this code — we already have a working system. We want to see how you build a real, stateful, two-sided feature end to end.
> 

### Scope

The domain below — statuses, offers, the window, the no-duplicate rule — is fully specified; implement it as described. Everything the spec doesn't dictate (where validation lives, how you model the lifecycle in code, the client/server contract, how you handle a stale edit, what the link encodes, how you split the internal vs. shopper representation) is your call. There's no single correct design; make choices you can explain and note them in `TECH_NOTES.md`.

---

## 2. The domain (fixed)

A **Campaign** has:

- `name`, `description`
- a **window**: `starts_at`, `ends_at`
- a set of attached **offers** (from the catalog below, each with parameters)
- a **status**: `draft` → `scheduled` → `live` → `ended` (forward-only)

**Status is the single source of truth for what a shopper sees.** A campaign is **enrollable when, and only when, `status == live`**. The window (`starts_at`, `ends_at`) is run-date metadata that is validated at launch — it does **not** auto-transition status, and you do **not** need a scheduler or background job. A `live` campaign whose `ends_at` has passed stays `live` (and enrollable) until someone explicitly ends it; that's expected for a single team that ends its own campaigns.

| Status | What it means | Editable? | Shopper-visible? |
| --- | --- | --- | --- |
| `draft` | being built | freely | no |
| `scheduled` | validated and locked, awaiting launch | no (locked) | no |
| `live` | enrollment open | no (locked) | **yes — enrollable** |
| `ended` | closed (terminal) | no | shown as ended, no offer |

**Transitions are explicit server actions:**

- `schedule` — `draft → scheduled`. Requires a valid window and ≥1 offer. Use this to stage a campaign with a future `starts_at`.
- `launch` — `→ live`. Allowed from `draft` or `scheduled` (scheduling first is optional). Requires a valid window and ≥1 offer. Opens enrollment immediately, regardless of `starts_at`.
- `end` — `→ ended`. Closes enrollment.

Only these **legal** transitions may happen, and they are **forward-only** — there is no "un-schedule" or re-edit of a non-draft campaign (fixing a typo on a scheduled/live campaign is out of scope). A campaign with **no offers** or an **invalid window** (ends before it starts, or already in the past) is **not launchable**. Editing is allowed in `draft` only.

### Offer catalog (fixed — each carries parameters)

You do **not** build an engine that runs these. But the parameters below **must** be captured in the builder and rendered on the shopper page — a bare type with no values is not acceptable.

| Type | Parameters to capture & display |
| --- | --- |
| `PRODUCT_PERCENT_DISCOUNT` | `percent` (e.g. 10), `applies_to` (free-text SKU list / label) |
| `CART_FIXED_DISCOUNT` | `amount_off`, `min_basket` threshold |
| `STICKER_EARN` | `stickers`, `per_amount` spent |

A campaign may attach **multiple offers, including more than one of the same type** (offers are a list, not keyed by type). Monetary fields are plain numbers in a single implied currency — no FX, no minor-units handling. `applies_to` is a free-text display label; you do **not** validate it against a real SKU catalog. All timestamps are **UTC**; no timezone handling is required on either surface.

### Distribution & enrollment (fixed)

- A **live** campaign can be **distributed** via a shareable link, rendered as a **QR code**.
- A shopper opens that link and **enrolls** by submitting an **identity** (phone or email). Identity is **unverified by design** — no password, no OTP. Anyone may claim any phone/email; treat that as an accepted property, not a bug to fix.
- A **pragmatic normalization** is enough for dedup: trim + lowercase for email, strip spaces/punctuation for phone. You do **not** need full E.164 / `libphonenumber`.
- An **enrollment** ties one normalized identity to one campaign. The same identity enrolling again in the same campaign must **not** create a duplicate — it should be recognized. Enrolling records membership and shows the offers; it does **not** generate a coupon or code.

---

## 3. What you'll build (MVP)

Use any stack; document how to run it. Any store is fine — SQLite, an embedded/file, or in-memory DB all work. Assume a **single process**; you don't need to design for horizontal scaling, so a unique constraint plus a version/`updated_at` check is enough for the duplicate-enrollment and stale-edit cases.

### Internal — the builder

1. **List campaigns** with status. Get the empty state right. (Filtering optional; no pagination needed.)
2. **Create & edit a campaign** — name, description, window, attached offers (add/remove from the catalog, **with their parameters**). Validate input; decide where validation lives.
3. **Lifecycle transitions** — schedule, launch, end. Only **legal** transitions may happen; the rules (can't launch an empty/invalid campaign, can't edit anything past `draft`) are **enforced on the server**, not just hidden in the UI. The UI reflects what's currently possible.
4. **Distribute** — for a live campaign, produce its shareable link and a scannable **QR code**.

### Public — the shopper page (mobile-first)

A page the QR/link opens that:

- if the campaign is **live** — shows the campaign, takes a shopper **identity**, enrolls them, and shows the attached **offer(s) with their values**;
- if the campaign is **not live** (draft / scheduled / ended) — shows the appropriate state, **not** the offer;
- if the shopper **already enrolled** (same normalized identity) — recognizes them instead of duplicating.

### Robustness & states

Handle the states that matter on both surfaces: loading, empty, validation feedback, error, actions disabled/blocked by status, a bad distribution link, and a duplicate enrollment. A **bad link** means one of two things: *invalid* — it doesn't resolve to a campaign (unknown/malformed) — or the campaign it resolves to simply isn't live (draft / scheduled / ended), which the public page renders as the appropriate non-live state. Links do **not** expire independently of the campaign; there's no separate link TTL. The public page is the one real shoppers would hit, so its states should hold up.

---

## 4. The decisions we're looking at

In `TECH_NOTES.md`, a short paragraph on **each**:

1. **Validation** — client, server, or both, and how you stop the two from drifting out of agreement.
2. **Lifecycle in code** — how you model the states and transitions, and how client and server agree on which transitions are legal *right now* (so the UI doesn't offer what the server will reject).
3. **Stale state** — a user opens a draft to edit; meanwhile someone else launches or ends it; they hit save. What happens, and what in your design makes that the outcome?
4. **The distribution link / QR** — what it encodes, what you deliberately *do not* expose in it, and how the public page handles a campaign that isn't live.
5. **Identity without auth** — what you accept as an identity, how you validate and **normalize** it, and what prevents a duplicate enrollment for the same identity + campaign.
6. **One model, two audiences** — how the shopper-facing representation of a campaign differs from the internal one, and where in your code you draw that boundary.

Finally: **what did you cut** for time, and why. Naming a limitation beats hiding one.

---

## 5. Deliverables

- A GitHub repo link or a ZIP — **include the `.git` folder**, we read commit history.
- `README.md`: how to set up, run, and use both surfaces.
- `TECH_NOTES.md`:
    - The six decisions above, plus what you cut.
    - How to exercise the flows, including at least one **blocked** action (e.g. launching an invalid campaign) and one **non-live scan** (opening the link for a draft or ended campaign).
    - Whether and how you used AI tools.
    - What you'd do next with more time.

---

## 6. Optional stretch goals

Pick **at most one or two**, only with time to spare. A clean MVP with strong notes beats a broad, shaky submission.

- **Enrollment count** — show, on the builder side, how many shoppers have enrolled. Keep it consistent as enrollments come in.
- **A live view** — a `live` campaign shows simple, refreshing activity (polled or streamed, mocked is fine) without hammering the server.
- **Real frontend craft** — accessible form errors, keyboard support, a public page that genuinely behaves on a phone.
- **Tests for the hard parts** — lifecycle transitions (legal and illegal), validation, duplicate enrollment, non-live scan.

---

## 7. Using AI tools

Use any AI tool you like, as you would on the job. One rule:

> **Don't submit code you can't explain.**
> 

In the review session we'll pick part of your code and ask you to change it live, explain why you put things where you did, and reason through a case we hand you. Mention your AI usage briefly in `TECH_NOTES.md`.

---

## 8. Review session

After an initial check that the MVP works, we'll do a one-hour session with the engineer you'd work most closely with. You'll walk through how to run it and the main flows on both surfaces, then we'll go through the feature together — including cases that probe §4 (expect a stale edit, an illegal transition, a scan of a non-live campaign, and a repeat enrollment). Be ready to debug a little with us.