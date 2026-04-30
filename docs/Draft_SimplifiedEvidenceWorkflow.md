# Draft: Simplified Evidence Workflow

## Purpose

This draft records a product simplification decision before more UI work is built on top of the current claim-heavy model.

The concern:

- the data model is becoming more correct than usable
- normal research work should not require users to think in terms of formal claims
- evidence, links, and agreed facts need to converge instead of becoming parallel layers

The proposed direction:

- make direct evidence linking the default workflow
- keep claims as an advanced provenance and disagreement layer
- treat agreed facts as the thing the main UI helps users reach

## Core Principle

The normal user flow should be:

1. select or create evidence
2. link it to the thing it supports
3. set confidence and add a short note when useful
4. move on

The UI should not require a separate "create claim" step for ordinary evidence work.

## Object Responsibilities

### Image

An image is source material.

It answers:

- where did this visual evidence come from?
- what does it show generally?
- what source, date, type, or provenance does it have?

### Image Region

An image region is the primary working evidence object for visual identification.

It answers:

- where is the visible thing?
- what object/entity is this region currently linked to?
- how confident is that direct link?
- what short note explains the link?

Primary fields should support:

- geometry
- label
- notes
- linked entity type/id
- confidence or review state
- attribution/history

### Image Link

An image link is whole-image evidence.

It answers:

- this image supports or relates to this entity as a whole

For example:

- image -> placement
- image -> kit
- image -> model

It should support:

- annotation/note
- confidence or review state if needed
- attribution/history if needed

### Placement

A placement is an agreed working fact about a donor part, kit, or assembly on a model.

It answers:

- what object is used?
- on which model/map?
- where is it positioned?
- how confident is the current record?
- what evidence supports it?

The placement page should show supporting evidence directly, not require users to mentally assemble it from claims.

### Claim

A claim is an advanced assertion layer.

It is useful for:

- contested interpretations
- alternative hypotheses
- detailed rationale
- review workflows
- source-extract arguments
- preserving why a fact was accepted, rejected, or superseded

It should not be the default action for ordinary linking.

## UI Rule

Primary UI actions should use simple evidence language:

- `Link entity`
- `Mark as evidence`
- `Link image to placement`
- `Set confidence`
- `Add note`
- `Accept`
- `Reject`

Advanced or secondary UI can expose claim language:

- `Show claims`
- `Add detailed claim`
- `Mark contested`
- `Review rationale`

## Maps Slice Implication

For `map_workbench.html`, the primary workflow should be:

1. select placement
2. inspect current position and position history
3. link image evidence directly to the placement
4. optionally set confidence/note on that evidence link
5. open linked image/region in the image workbench when more detail is needed

The current "Create placement claim" action should be demoted or renamed.

Preferred primary wording:

- `Mark linked image as evidence`

Potential implementation:

- create or update an `image_link`
- store note/confidence on the evidence link when supported
- optionally create a claim only in an advanced/details section or when the user marks the evidence as contested

## Image Workbench Implication

For `workbench.html`, the primary region workflow should be:

1. select or draw region
2. link the region directly to kit/part/placement/model
3. set confidence/review state
4. add a short note

The current claim form should be secondary.

Preferred presentation:

- primary section: `Linked entity`
- primary fields: confidence, note, review state
- secondary section: `Detailed claims`

## Convergence Rule

Direct links and placements are the working facts.

Claims are supporting arguments, conflicts, or review records.

The UI should always answer:

- what is the current accepted link/fact?
- what evidence supports it?
- are there contested or rejected alternatives?

Accepted claims may explain a fact, but users should not have to create a claim before a useful fact exists.

## Near-Term Product Changes

Recommended next steps:

1. Reword claim-heavy UI in the active workbenches.
2. Demote "Create claim" from primary action to secondary/details.
3. Add confidence/review state directly to region/entity links where practical.
4. Add confidence/review state directly to image/entity links where practical.
5. Keep existing claim APIs and tables for advanced provenance, but stop making them the center of the normal workflow.

## What Not To Do Yet

- do not delete the claims table
- do not rewrite old claim data immediately
- do not build a complex review queue before the simplified direct-link workflow feels good
- do not make users choose between "region link" and "claim" for ordinary work

## Open Questions

- Should direct region links get their own `confidence` and `status` fields, or should those stay on the region record?
- Should `image_links` get `confidence`, `status`, `attributed_to`, and timestamps?
- Should accepted claim creation be automatic when a direct link is marked accepted, or remain manual/advanced?
- How much claim UI should remain visible in the first-pass operator workbenches?
