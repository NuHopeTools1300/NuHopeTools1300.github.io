# UI Principles

## Purpose

This document defines the core UX principles for NuHopeTools as a research workstation.

It is meant to guide screen design, interaction decisions, and implementation tradeoffs as the product moves away from fragmented legacy tools toward a coherent workbench.

## The Product Is A Workbench

NuHopeTools should behave like a professional research environment, not a marketing site and not a generic CRUD dashboard.

The user is doing investigative work:

- comparing evidence
- annotating evidence
- linking entities
- preserving provenance
- forming or reviewing claims

The interface should support concentration, structured thinking, and repeatable expert workflows.

## Core Principles

### 1. One Main Workspace

Each screen should have one clear primary workspace.

The baseline layout is:

- `Library`
- `Canvas`
- `Inspector`

Users should not feel like they are juggling multiple unrelated tools inside one page.

### 2. Evidence First

Always distinguish between:

- evidence
- entity
- interpretation

Examples:

- image = evidence
- region = evidence unit
- kit or placement = entity
- claim = interpretation

The interface should never make it ambiguous whether something is a fact, a note, or an interpretation.

### 3. Stable Identity

Objects should present consistently everywhere.

A `kit`, `image`, `region`, `claim`, or `source` should have:

- a stable label
- stable metadata treatment
- stable badge logic
- stable inspector structure

Users should not have to relearn an object when they encounter it in a new view.

Stable identity also means reversibility:

- if a region can link to a kit
- then a kit should be able to show all linked regions

The system should support moving in both directions between evidence and entities.

### 4. Provenance Is Not Secondary

For this project, provenance is core content.

Every important screen should make it easy to see:

- source
- attribution
- confidence
- status
- history

If the user has to hunt for provenance, the UI is failing the research model.

### 5. The Canvas Is For Direct Work

If the user is working with an image, map, or timeline, the main interaction should happen on the central canvas.

Examples:

- selecting a region on an image
- inspecting a map location
- reading a transcript extract
- scrubbing through a timeline

Do not force canvas work into side-form workflows when direct manipulation is possible.

### 6. The Inspector Is For Meaning

The inspector should answer:

- what is selected
- what does it mean
- what is it linked to
- what can I do next

It should not become a random stack of controls.

Primary editing controls do not always belong in the far-right inspector.

When the user selects from a list or object browser, the highest-frequency editing controls should
usually stay close to that selection source:

- list or browser first
- compact selected-object editor directly nearby
- far-right inspector for deeper detail, history, provenance, and linked evidence

This is especially important for object-focused workflows, where a wide `select on the left / edit
on the far right` split makes editing feel detached and unnatural.

### 7. Progressive Disclosure

Show what matters first.

Reveal deeper metadata and advanced actions only when needed.

This keeps the interface readable without hiding important power.

### 8. Low-Friction Linking

Linking evidence to real entities should be:

- searchable
- fast
- reversible
- visible

This is one of the highest-frequency expert actions in the whole product.

The reverse lookup path should be equally first-class:

- starting from a kit, placement, location, or object
- finding all linked evidence
- following that evidence into related claims and neighboring entities

### 9. Empty States Must Suggest Action

A blank state should tell the user what the next useful step is.

Good examples:

- no image selected
- no regions yet
- no linked entity
- no claims yet

These states should feel like guidance, not absence.

### 10. Conflict Must Be Representable

The project contains disagreement and uncertainty by nature.

The UI must be able to show:

- multiple claims on one region
- different confidence levels
- unresolved identities
- contested interpretations

Conflict is part of the subject matter, not an error condition.

## Layout Principles

### Global Structure

- top bar for scope, global navigation, and global actions
- left for library and filters
- center for the main canvas
- right for inspector and actions tied to selection

### Panel Behavior

- library should support scanning and filtering
- canvas should support direct manipulation
- inspector should change with selection, not with page navigation
- primary editing should stay near the selection source when possible
- far-right panels should bias toward secondary detail rather than carrying every working control

Across the product, surfaces should feel interoperable rather than siloed:

- the same object should open cleanly from multiple starting points
- a user should be able to pivot from image -> kit, kit -> image, placement -> map, map -> evidence without feeling they changed products

### Modal Use

Prefer inspector-based workflows over modals.

Use a modal only when:

- the action is narrow
- temporary focus is helpful
- the user should not continue browsing while it is open

### Density

The product should tolerate high information density, but not visual chaos.

Use density for:

- metadata
- provenance
- linked entities

Do not use density as an excuse for poor hierarchy.

## Component Principles

### Cards

Cards should summarize one object clearly and consistently.

Typical card types:

- evidence card
- entity card
- claim card
- event card

### Chips And Badges

Use small badges for:

- confidence
- source type
- category
- review status
- attribution markers

Badges should carry meaning, not decoration.

### Lists

Lists should support quick scanning.

Good list row content:

- title
- subtitle
- key badges
- counts
- time/provenance snippet

### Forms

Forms should be used only where structured input is genuinely needed.

They should not become the default replacement for better canvas interactions.

## Interaction Principles

### Selection Model

The user should always know:

- what page scope they are in
- what item is selected in the library
- what item is selected on the canvas
- what the inspector is currently showing

### Keyboard And Speed

The eventual product should support fast expert use:

- keyboard search focus
- quick next/previous navigation
- annotation shortcuts
- fast linking actions

This does not all need to exist in the first slice, but the interaction model should allow it.

### Undo / Reversibility

Actions that create links, annotations, or claims should feel safe.

Support:

- easy correction
- visible edit history
- low fear of experimentation

## Visual Principles

### Tone

The product should feel:

- archival
- technical
- serious
- calm

Not:

- toy sci-fi
- fandom novelty
- glossy startup dashboard

### Color

Use color to encode meaning:

- selection
- confidence
- review state
- evidence vs interpretation

Avoid using color as decoration only.

### Typography

Typography should prioritize:

- legibility
- hierarchy
- metadata readability
- dense but calm research reading

### Motion

Motion should be restrained and functional.

Use it for:

- panel transitions
- selection continuity
- context preservation

Avoid decorative motion.

## Implementation Principles

### Build The Shell First

Do not redesign object screens one by one without a common shell.

### Build Vertically

Start with one end-to-end slice that proves:

- browse
- inspect
- annotate
- relate

### Keep Legacy Tools Operational

Use current tools to keep research moving, but avoid major design investment in them.

### Standardize Before Beautifying

Visual polish should follow interaction clarity, not replace it.

## Working Rule

If a design decision makes the interface prettier but less explicit about evidence, provenance, or identity, it is the wrong decision for this product.
