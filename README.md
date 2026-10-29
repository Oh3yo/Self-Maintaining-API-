# Self-Maintaining API

> *The code shouldn't break just because someone has modified it.*

Third-party APIs change all the time and when a field gets renamed, an endpoint disappears, a function suddenly wants a new argument, and find it out when the production breaks. This project watches those APIs, finds the code in the repo that depends on whatever changed, and writes the fix.


## Highlights

- **Spots breaking changes early** by diffing OpenAPI specs, changelogs and SDK versions
- **Finds exactly where you use the changed thing** (real AST parsing for Python, regex for other languages)
- **Writes the patch for you** using an LLM, then checks it against your own tests
- **Never touches your working copy**. Patches are tested on a temporary copy first
- **Can open the pull request too**, so all that's left is the review
- **Tests run offline** with a fake model, so no API key is needed to try them


## Overview

The whole thing is four small scripts that pass JSON to each other:

```
detector.py  ->  impact_scanner.py  -> fix_generator.py  ->  pipeline.py
what changed     where it's used        propose a fix        test it and ship it
```

1. **Detect.** `detector.py` fetches each API listed in `apis.yaml`, compares it to the last snapshot it saved, and labels every difference as `breaking`, `warning` or `info`. 
2. **Scan.** `impact_scanner.py` searches the repo for the endpoints and fields that had changed, and scores each match by how likely it is to be a real usage.
3. **Fix.** `fix_generator.py` sends the affected code to a model on [Nebius Token Factory](https://tokenfactory.nebius.com/). The model doesn't write a diff, since LLMs are bad at line numbers. It returns SEARCH/REPLACE edits, and the script builds the real diff itself. If an edit doesn't match or the tests fail, the error goes back to the model for another try (up to 3).
4. **Ship.** `pipeline.py` runs the repo's tests on a temp copy with the patch applied and writes `fix.patch`. Add `--pr` and it also pushes a branch and opens a GitHub pull request.

### What it looks like

There's a small demo built in. A mock API renames `User.email` to `email_address`, and the pipeline notices, finds `user["email"]` in `demo_repo/client.py`, and patches it:

```diff
-    return user["email"]
+    return user["email_address"]
```


## Usage

Check for changes in the APIs listed in `apis.yaml`:

```bash
python detector.py run --config apis.yaml --once
```

Scan a repo and generate a fix:

```bash
python pipeline.py path/to/your/repo changes.json -o fix.patch
```

Same thing, but also open a pull request:

```bash
python pipeline.py path/to/your/repo reports --pr
```

`changes.json` can be the detector's output, or you can write it by hand:

```json
[{"kind": "field_renamed", "schema": "User", "field": "email", "new_name": "email_address"}]
```

Want to compare two specs without any config?

```bash
python detector.py diff old_spec.json new_spec.json
```

### Try the live demo

```bash
python dashboard.py            # then open http://localhost:8001
python dashboard.py --no-pr    # practice run: stops at the patch, no PR
```

The dashboard starts the mock API for you. Break it with one click, then watch the detector, scanner and fixer do their thing.


## Installation

You'll need Python 3.9 or newer.

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
pip install -r requirements.txt
```

Then set your keys as environment variables:

```bash
# macOS / Linux
export NEBIUS_API_KEY=your_key_here
export GITHUB_TOKEN=your_token_here      # only needed for --pr

# Windows (cmd)
set NEBIUS_API_KEY=your_key_here
set GITHUB_TOKEN=your_token_here
```

| Variable | What it's for |
|---|---|
| `NEBIUS_API_KEY` | Required to generate fixes |
| `GITHUB_TOKEN` | Opening pull requests (also avoids GitHub rate limits in the detector) |
| `CHANGE_WEBHOOK_URL` | Optional, get pinged when something breaking is found |
| `FIX_MODEL` | Optional, use a different model |

Keys are only ever read from your environment. Nothing is stored in this repo, so please keep it that way and don't commit them.


## Running the tests

```bash
python -m pytest -q
```

No network or API key needed.


## What's in here

| File | What it does |
|---|---|
| `detector.py` | Diffs specs, changelogs and SDK versions |
| `impact_scanner.py` | Finds code affected by a change |
| `fix_generator.py` | Asks the model for a fix and validates it |
| `pipeline.py` | Runs everything end to end and opens the PR |
| `dashboard.py`, `mock_api.py`, `demo_repo/` | The demo setup |
| `apis.yaml` | The APIs you want to watch |


## Feedback

Found a bug, or have an idea? Open an issue. Please let me know, I'll be happy to get feedback.

Generated pull requests are meant to be reviewed, not blindly merged. Please give them a look before you hit the button.


## Author

Made by Oheyo Talem (https://github.com/Oh3yo).
