# Tech Notes

## 1. Validation

Every input path (campaign details, each offer type, the shopper's identity) is validated through a
Django `Form`/`ModelForm` in `campaigns/forms.py`, and each form's `clean_<field>()` delegates the
actual "is this acceptable" decision to a small set of shared functions in `campaigns/validators.py`
and `campaigns/utilities.py` (`validate_positive`, `validate_non_negative`, `validate_name_unique`,
`normalize_identity`). Client and server can't drift apart because the widget attributes that drive
HTML5 validation (`min`, `max`, `step`, `required`) are built from the *same constants* those
functions use — e.g. `PercentDiscountOfferForm`'s widget reads `max=str(validators.PERCENT_MAX)`,
the exact bound `clean_percent()` enforces. There's one number, not two independently maintained
copies.

That covers input shape. State legality (can this campaign be edited right now, is this transition
allowed) isn't something a Form can check — it's enforced on `Campaign` itself: `Campaign.save()`
calls `self.full_clean()` before every write, and `Campaign.clean()` re-derives the same rules
`services.py` and `selectors.py` already use (see §2). Because `ModelForm.is_valid()` already calls
`instance.full_clean()` internally with no extra save, this comes for free on every form submission —
including from Django admin — with no "save just to validate" cost.

## 2. Lifecycle in code

`campaigns/transitions.py` holds two tables that are the single source of truth for the whole
lifecycle: `LEGAL_TRANSITIONS` (`draft → {scheduled, live}`, `scheduled → {live}`, `live → {ended}`,
forward-only) and `EDITABLE_STATUSES` (currently just `draft`). Three layers all read the same
tables instead of each hand-rolling their own copy of "is this legal":

- **Read side** — `selectors.py`'s `can_schedule`/`can_launch`/`can_end`/`can_edit` consult
  `transitions.py` plus `validators.window_is_valid_for_launch`/`offers_present`, and
  `available_transitions()` bundles them into one dict. The builder template only renders a
  Schedule/Launch/End button when the matching flag is true — an illegal action is never offered,
  not just disabled.
- **Write side** — `services.schedule/launch/end` build their atomic `UPDATE ... WHERE status IN
  (...)` clause from `transitions.legal_sources_for(target_status)`, so the actual DB write can only
  succeed from a legal source status.
- **Backstop** — `Campaign.clean()` (run by `save()`) re-checks `is_legal_transition()` and
  `is_editable()` against the same tables. This exists for callers that don't go through
  `services.py` at all — Django admin's `CampaignAdminForm` writes straight to the ORM, so it's the
  model, not the admin form, that actually stops an illegal edit.

## 3. Stale state

Every builder mutation carries the `updated_at` the browser last saw as `expected_updated_at`.
Services perform a single atomic `UPDATE campaigns SET ... WHERE pk = %s AND updated_at = %s [AND
status IN (...)]` — if a concurrent request already moved the row, that `WHERE` matches zero rows,
so the mutation makes no change and the code proceeds to `_diagnose_write_failure()`, which re-reads
the row purely to explain *why* (this is only for the error message; the `UPDATE`'s `WHERE` clause is
what actually decides correctness, so there's no TOCTOU gap between the two). 

## 4. The distribution link / QR

The link is `/c/<token>/`, where `token` is a 12-byte `secrets.token_urlsafe()` value generated once
per campaign (`Campaign.token`) — unguessable and unrelated to the campaign's primary key, name,
offers, or status. Nothing about the campaign's contents or state is encoded in the link itself; the
QR is just that URL rendered as a PNG data URI (`utilities.qr_code_data_uri`). Maybe if the campaign had more detials, that are to be displayed on the page, without hitting the server, we could have encoded in the QR code. Not a lot of detials but a few. 

## 5. Identity without auth

`EnrollForm.identity` accepts one free-text string. `utilities.normalize_identity()` decides what it
is: containing `@` makes it an email (lowercased, checked against a permissive regex); anything else
is treated as a phone number (stripped to digits, required to be exactly 10 digits — a deliberately
simple rule per spec, not full E.164). The raw text the shopper typed is kept in `raw_identity` for
display; the normalized form drives lookups and dedup. Duplicate prevention is a genuine DB
constraint — `UniqueConstraint(fields=["campaign", "normalized_identity"])` — not just an
application-level check, and `services.enroll()` calls `get_or_create()` on that same pair, so a
second enrollment attempt (or a race that loses a concurrent insert) is *recognized* rather than
rejected or duplicated: the shopper sees "Welcome back" instead of a second row. The same identity
enrolling in a *different* campaign is unaffected, since uniqueness is scoped to the
(campaign, identity) pair, not the identity alone.

## 6. One model, two audiences

Both surfaces query the same `Campaign`/`Offer` rows — there's no separate public DTO or serializer —
the boundary is drawn in each view's context-building function, not on the model. `builder.views.
_build_context()` always includes internal-only data: the `transitions` dict, `enrollment_count` /
`live_activity`, the editable `ModelForm`, and the distribution link + QR. `shopper.views.
_build_context()` collapses everything down to exactly one of three states (`invalid` / `not_live` /
`live`), and the `live` state's context is deliberately thin — campaign name/description/window,
offers, and an enroll form; no `updated_at`, no transitions, no other shopper's identity. The one
thing shared verbatim between the two templates is `offer_summary` (`templatetags/offer_tags.py`),
so the offer text a shopper is promised can never drift from what the retailer sees while building
it — everything else about "what's visible" is a per-surface view decision, not a field hidden on
the model.

## What I cut for time

- **Editing an existing offer's parameters.** Only add/remove is supported; fixing a typo in an
  offer means removing it and re-adding it. Given `draft`-only editability already exists, wiring an
  in-place `update_offer` would have been incremental, but it didn't make the cut.
- **Pagination/filtering on the campaign list.** Explicitly optional per spec; fine at demo scale, a
  real backlog of campaigns would need it.
- **A real API layer.** Referenced in a comment (`Campaign.clean()`) as a "what if" — the model-level
  enforcement was built so that a future API would inherit the same guarantees for free, but no REST
  endpoints were actually built; the two Django views are the only write paths.
- **Push-based live activity.** The "recent enrollments" view (stretch goal) polls every 5s while a
  viewer opts in, rather than pushing over SSE/websockets — the spec explicitly allows this, and it
  avoids holding an open connection per idle viewer.
- **Handling  Stale state** - Rightnow doing it with comparing the last updated timestamp, but may I would maintain a incremental version and check for this clash.

## AI tool usage

Built with Claude as a pair-programming tool 
- Wrote Code 
- Wrote tests
- Generated templates

## What I'd do next with more time

- A better caching. Improve on scalability 

- With more time, I'd expland on the business usecase like
  - Maybe a Brand / retailer login
  - Reward points for customers 
  - static assets support on the offering page
