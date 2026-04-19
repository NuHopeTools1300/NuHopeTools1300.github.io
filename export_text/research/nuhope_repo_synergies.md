# NuHopeTools Synergies - First Pass

## Repo Seen

- Path: `C:\Users\gunkel\git_nht\NuHopeTools1300.github.io`
- This is a real git repo with:
  - `backend`
  - `docs`
  - `tools`
  - `README.md`
  - spreadsheets like `ANH donors.xlsx` and `PartList_private.xlsx`
- From the `README`, the project is already framed as an `ILM Van Nuys Kit-Bash Research Platform`

## Why This Is A Strong Fit

- The repo is already trying to turn fragmented studio-model knowledge into structured, cross-linked research.
- Our current ANH research work is doing the same thing from a different angle:
  - `timeline`
  - `model variants`
  - `physical lineage`
  - `image evidence`
  - `who built what`
- That means these tracks are not parallel hobbies. They can feed each other directly.

## The Best Synergies

### 1. The PPTX image work fits the repo's existing image model

The repo already describes:
- `images`
- `image_tags`
- `image_links`
- `contributors`

That is almost exactly what the new `anh_pptx_image_manifest` wants to become.

Practical direction:
- import each reviewed PPTX image as an `image`
- tag it by:
  - `model`
  - `shop photo`
  - `documentary frame`
  - `workbench`
  - `Death Star`
  - `Landspeeder`
  - `X-Wing`
- link it to:
  - `models`
  - future `timeline events`
  - contributors or source chains when known

### 2. The ANH timeline exposes a missing concept in the repo: events

From the README, the backend is strong on:
- kits
- parts
- placements
- images
- models

But the research we are building depends heavily on a different object type:
- `event`

Examples:
- `Blue 1 shipped to England on 1975-12-26`
- `maroon TIE comp test on 1976-03-06`
- `Y-wing Number One buck begins spring 1976`
- `Death Star cannon tied to first completed ILM shot`

That suggests a very valuable future addition:
- `events`
- `event_links`
- maybe `sources`

Suggested minimum event fields:
- `id`
- `title`
- `start_date`
- `end_date`
- `date_precision`
- `event_type`
- `summary`
- `confidence`
- `notes`

Suggested event links:
- event to `model`
- event to `image`
- event to `contributor`
- event to `source`

### 3. The repo is Falcon-first, but our research broadens it into an ANH production graph

The repo README says it starts with the `5-foot Millennium Falcon`.
Our current research already builds out:
- `X-Wings`
- `Y-Wings`
- `TIE Fighters`
- `Landspeeder`
- `Sandcrawler`
- `Blockade Runner`
- `Escape Pod`
- `Death Star` surface systems and special sections

That means a clean future direction is:
- keep Falcon as the deepest dataset
- but make the platform visibly `ANH-wide`

This is a big strategic win, because cross-model donor logic becomes more interesting when the tool can connect:
- Falcon donors
- X-wing donors
- Y-wing donor reuse
- Death Star kit usage
- shop-period image evidence

### 4. The current HTML timeline can become a prototype, not just an artifact

Right now:
- `anh_ilm_timeline_visual.html` is a standalone research page

But conceptually it already behaves like a product prototype for NuHopeTools:
- date-banded research wall
- clickable event cards
- image rail
- confidence-aware interpretation

Future direction:
- port the timeline into the repo as a real tool page
- make it data-driven from backend content
- let users filter by:
  - model
  - year
  - evidence strength
  - object type
  - person

### 5. The image annotator could do more than part IDs

The repo already includes an `Image Annotator`.

Right now it sounds aimed mainly at part-location work.
But for the ANH research we are doing, the same annotator could support:
- `this is Blue 1 state`
- `this is a Red 2 repaint`
- `Death Star crane visible here`
- `Landspeeder engine pod removed`
- `shop personnel identified here`

That is a major synergy:
- one image tool
- multiple research layers
- parts, models, states, and chronology all on the same image

### 6. The project would benefit from a claim-based research layer

A lot of ANH research is not binary fact.
It looks more like:
- `claim`
- `counterclaim`
- `confidence`
- `source trail`

The Y-wing work is the clearest example:
- `Gold Leader / TIE Killer`
- `Tiger Sprockets`
- `Magic of Myth`
- `Gold Two`
- `Triangles`

That suggests a future schema direction beyond `placements`:
- `claims`
- `claim_links`
- `claim_sources`

This would let the repo store:
- stable facts
- contested hypotheses
- superseded interpretations

without flattening them into one forced answer too early.

## Concrete Near-Term Directions

### Option A: Use the repo as the home for the image manifest first

This is probably the easiest win.

Do next:
1. turn `anh_pptx_image_manifest.csv` into importable image metadata
2. map each reviewed image to a `model`
3. tag reviewed images by `subject`, `program`, and `confidence`
4. expose them through the existing image tooling

Why this is strong:
- low schema risk
- high immediate payoff
- gives the repo more real research content quickly

### Option B: Add an event layer and move the timeline into the platform

Do next:
1. define `events` table
2. define `event_links`
3. seed from:
   - `anh_ilm_timeline.csv`
   - `anh_ilm_model_timeline.csv`
   - `anh_ilm_people_crosswalk.csv`
4. adapt or extend `tools/image_timeline.html`

Why this is strong:
- it turns the repo from a part database into a true research platform
- it lets image evidence and chronology reinforce each other

### Option C: Build an ANH evidence graph

This is the most ambitious and probably the most exciting.

Nodes:
- models
- images
- events
- parts
- assemblies
- people
- sources
- claims

Edges:
- `shows`
- `built_by`
- `likely_dates_to`
- `supports`
- `contests`
- `derived_from`
- `reused_on`

That would make NuHopeTools genuinely different from a normal model-reference site.

## My Current Recommendation

If we want the highest signal with the lowest risk, the best order is:

1. integrate the reviewed PPTX images into the repo's image system
2. add a lightweight `events` layer
3. migrate the standalone ANH timeline into a repo-native tool
4. only after that, add deeper contested-claim logic

## Most Important Insight

The repo and this research are already speaking the same language.

The repo starts from:
- `what kit part is this?`

Our current ANH work adds:
- `when did this exist?`
- `which physical object was it?`
- `who built it?`
- `what image proves it?`
- `how certain are we?`

Put together, that becomes much more powerful than either one alone.
