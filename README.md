# Looplink Starter Project
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Django project using front-end libraries:

- [HTMX](https://htmx.org/)
- [Alpine](https://alpinejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)

---

## LoopLink: Campaign Builder & Shopper Enrollment

This repo implements the LoopLink take-home exercise: an internal **Campaign Builder** (retailer/brand
side) and a public, auth-free **shopper enrollment page**. There's a single workspace, no
multi-tenancy, no login for either side. See `TECH_NOTES.md` for the design decisions behind the
lifecycle, validation, stale-edit handling, distribution link, identity normalization, and the
internal/shopper split.

### Running it

Complete **Dev Environment Setup** below, then:

```sh
./manage.py migrate
./manage.py runserver
```

Visit [http://localhost:8000/](http://localhost:8000/) — the home page has two entry points:

- **"Open the Campaign Builder"** → `/builder/`, the retailer/brand side.
- **Shopper side** has no standalone link on the home page by design — a real shopper always arrives
  via a specific campaign's link/QR, not a generic landing page. Launch a campaign in the Builder to
  get one (see below).

### Using the Builder (retailer/brand)

1. `/builder/` → **New Campaign** creates a draft with a placeholder name and a default one-week window.
2. Open it, edit name/description/window, **Save**.
3. Add at least one offer (pick a type — percent discount, cart discount, or sticker-earn — fill in
   its parameters, **Add offer**). Offers can be added or removed; editing one in place isn't
   supported yet (see `TECH_NOTES.md`, "what I cut").
4. **Schedule** or **Launch** appear only once the campaign has ≥1 offer and a valid window (`ends_at`
   in the future, after `starts_at`) — this is `selectors.available_transitions()` deciding what's
   currently legal, not a static button.
5. Once `live`, a **Distribute** panel appears with the shareable link and its QR code.
6. **View live** shows enrollment count and the most recent enrollments, polling every 5s while open.
7. **End** closes enrollment. All of `draft → scheduled → live → ended` is forward-only — there's no
   "un-launch."

### Using the shopper page

1. Open a live campaign's link (from its Distribute panel), or scan the QR.
2. Enter a phone number (10 digits) or an email, submit — you're enrolled and see the offer(s).
3. Submit the same identity again (reload the page, submit again) — you're recognized ("Welcome
   back!") instead of creating a second enrollment. A different identity on the same campaign, or the
   same identity on a different campaign, enrolls independently.

### Exercising a blocked action

The Builder UI never *offers* an illegal action — the Schedule/Launch/End buttons simply don't render
until the underlying rule is satisfied. To see the server actively reject an illegal state (not just
hide a button for it), use Django admin, which writes to `Campaign` directly with no button-hiding to
fall back on:

1. `python manage.py createsuperuser`, then sign in at `/admin/`.
2. Open a `draft` campaign that has **zero offers**, change its **Status** to `live`, save — rejected:
   *"Add at least one offer before launching."*
3. Open a **live** campaign, change its **Status** back to `draft`, save — rejected: *"Cannot go from
   live to draft."* Both rejections come from `Campaign.clean()` (see `TECH_NOTES.md` §2), so the same
   protection applies no matter which surface — Builder, admin, or a future API — makes the request.

### Exercising a non-live scan

1. Launch a campaign in the Builder and copy its distribution link from the Distribute panel.
2. Click **End** on that same campaign.
3. Revisit the copied link — the token still resolves, but the page now shows the campaign as
   **ended** (no offers, no enroll form) instead of what it showed while live. The same thing happens
   for a `draft` or `scheduled` campaign if you have its token.
4. Visit `/c/does-not-exist/` (any token that isn't real) — renders a 404 "Link not found" state
   instead of an error page.

### AI tool usage

Built with **Claude Code** (Anthropic) as a pair-programming tool for essentially the whole project —
architecture and design tradeoffs (where validation should live, how to model the lifecycle so the UI
and server can't drift apart, how to handle a stale edit, the model-level enforcement described in
`TECH_NOTES.md` §§1–3) were worked through in conversation rather than generated wholesale from a
one-line prompt. A couple of concrete examples: the model-level `Campaign.clean()` backstop went
through two iterations after an initial caching approach (`__init__`/`from_db`) turned out to silently
break under `refresh_from_db()`, caught by testing it rather than assuming it worked; and while writing
this README I found and fixed a real bug where a non-field validation error (`"offers"` isn't an
actual `Campaign` field) crashed any `ModelForm` that didn't declare that field, instead of failing
validation gracefully. I can walk through and defend any part of this codebase.

### What's next with more time

See `TECH_NOTES.md` for the full list; top of it would be in-place offer editing, a real API layer
behind the same `services.py`/model guarantees the two UIs already share, and push-based (rather than
polled) live activity.

---

## Where to Look First

If you're new to this project, here are some good starting points:

- **Complete the Dev Environment Setup**
  - The instructions are in the following section.
  - Once complete, you can run `python manage.py runserver` and visit [http://localhost:8000](http://localhost:8000)

- **Using Version Control?**
  - TIP: Make sure you `git init` (or equivalent in mercurial, svn, etc.) and make an initial commit before you add your code to make future commits readable.

- **Default view (landing page)**  
  - Python view: `looplink/ui/base/views.py` (the `default` view)  
  - Template: `looplink/ui/base/templates/base/default.html`

- **HTMX example flow**  
  - Python view: `looplink/ui/base/views.py` (the HTMX example view using `DjangoHtmxActionMixin`)  
  - Entry point: `js_entry` named `base/htmx_example`  
  - Templates:
    - `looplink/ui/base/templates/base/htmx_example.html`
    - `looplink/ui/base/templates/base/partials/htmx/initial_state.html`
    - `looplink/ui/base/templates/base/partials/htmx/step_two.html`
    - `looplink/ui/base/templates/base/partials/htmx/step_three.html`

- **JavaScript and styles**  
  - JavaScript entry points are referenced via the `js_entry` template tag.  
  - App/module-specific assets live in an `assets` folder (for example, `looplink/ui/base/assets/`).  
  - Global styles live in the `styles` folder at the project root (for example, `styles/looplink.css`), which also includes the Tailwind CSS setup.

---

## Dev Environment Setup

### Prerequisites

#### Invoke

This project uses [Invoke](https://www.pyinvoke.org/) for dev automation. Once step 1 below is complete, you can view the list of
available commands with:

```sh
inv -l
```

New commands and updates can be made in the `tasks.py` file.

#### UV

Python dependency management uses [`uv`](https://docs.astral.sh/uv/).

There are [several ways to install `uv`](https://docs.astral.sh/uv/getting-started/installation/). Use whatever method works best for your platform.

- **Linux**

  Ubuntu:

  ```sh
  sudo snap install astral-uv
  ```

- **Mac**

  First install [Homebrew](https://brew.sh/), then use it to install `uv`:

  ```sh
  brew install uv
  ```


### STEP 1: Install Python dependencies

> Python 3.13 is required.

Create a virtualenv with `uv`:

```sh
uv venv
```

Activate the environment:

```sh
source .venv/bin/activate
```

Install Python dependencies:

```sh
uv sync --compile-bytecode
```


### STEP 2: Run the automated initial environment setup

```sh
inv setup-dev-env
```

### STEP 3: Have JavaScript and CSS (SCSS) automatically rebuild on changes

```sh
inv npm -w
```

> NOTE: Restart this command if you add a new `js_entry` path.


### STEP 4: Run the development server

```sh
./manage.py runserver
```


### STEP 5: View in browser

With everything running, visit:

```text
http://localhost:8000/
```

in your browser.

---

## Local Development Notes

Make sure you are using the correct virtual environment (see Dev Environment Setup):

```sh
source .venv/bin/activate
```

To bring up the Docker containers:

```sh
inv docker up
```

To bring down the Docker containers:

```sh
inv docker down
```

To rebuild Docker containers:

```sh
inv docker rebuild
```

To update requirements:

```sh
inv requirements
```

To run the development server (from the terminal):

```sh
python manage.py runserver
```


## Running Tests

To run tests:

```sh
pytest
```

To test a specific app/module:

```sh
pytest looplink/ui/dashboard/tests/test_something.py
```


## Recommended: Linting

We recommend the following linters. Configs are already provided.

- Python: [Ruff](https://github.com/astral-sh/ruff)
- JavaScript: [ESLint](https://eslint.org/)


## HTML Formatting

High-level:

- Two-space indentation
- Attribute line breaks

See [this HTML Guide](https://www.commcarehq.org/styleguide/b5/html/) for full details.


## CSS Formatting

- Two-space indentation


## Dependencies / Requirements

To add a new dependency, run:

```sh
uv add --dev PACKAGE_NAME
```

Alternatively, manually add it to `pyproject.toml`. After a manual edit, run:

```sh
uv lock
```

Update requirements with:

```sh
inv requirements
```
