# Documentation Index

Updated: May 3, 2026

This folder contains both current operating docs and older design/planning records. Use this index to avoid treating every document as equally current.

## Start Here

- [Project README](../README.md) - short setup and repository front door
- [Current Status](CurrentStatus.md) - active surfaces, current data shape, verification, immediate build lane
- [Roadmap](Roadmap.md) - strategic plan from private workstation to public platform
- [API Reference](API.md) - current Flask routes grouped by domain
- [Backend Architecture](BackendArchitecture.md) - current backend module boundaries
- [Data Model](DataModel.md) - canonical schema summary and schema-evolution rule
- [Deployment Plan](DeploymentPlan.md) - current hosting, storage, and access-control direction
- [Datasette](datasette.md) - local database browser sidecar
- [Migration Policy](../backend/migrations/README.md) - source-of-truth rule for schema changes

## Product Architecture

- [Product UI Architecture](ProductUIArchitecture.md) - target workstation shell and object model
- [UI Principles](UIPrinciples.md) - interaction and visual principles
- [Core Research Workflows](CoreResearchWorkflows.md) - workflow inventory and surface ownership
- [Workflow Pivot Table](WorkflowPivotTable.md) - user-question-to-surface mapping
- [Workflow System Map](WorkflowSystemMap.md) - compact system sketch
- [Wireframes: Image Workbench](Wireframes_ImageWorkbench.md) - image workbench screen sketches

## Active Workflow Notes

- [Kit-First Map Placement Workflow](KitFirstMapPlacementWorkflow.md)
- [Placement Refinement Workflow](PlacementRefinementWorkflow.md)
- [Position Correction Implementation](PositionCorrectionImplementation.md)
- [Image Families And Position Correction](ImageFamiliesAndPositionCorrection.md)
- [Entity Browser Implementation Plan](EntityBrowserImplementationPlan.md)
- [Draft: Simplified Evidence Workflow](Draft_SimplifiedEvidenceWorkflow.md)
- [Map Workbench Part Image Lessons](MapWorkbenchPartImageLessons.md)

## Completed / Historical Planning

- [Phase 1 Build Checklist](Phase1BuildChecklist.md) - completed Phase 1 and Phase 1.5 checklist
- [Workbench Slice: Image -> Region -> Entity -> Claim](WorkbenchSlice_ImageRegionClaim.md) - first vertical slice specification
- [Research Architecture](ResearchArchitecture.md) - evidence-first target architecture, including deferred entities

These are still useful, but current operational truth should come from [Current Status](CurrentStatus.md).

## Data, Imports, And Research Outputs

- [Kit Taxonomy](KitTaxonomy.md)
- [Donor Cleanup: Not In ANH Donors](DonorCleanup_NotInANHDonors.md)
- [COLMAP Transform Guide](colmap_transform_guide.md)

Generated review artifacts live in [generated](generated/):

- `generated/KitBoxImageMatchDryRun.csv`
- `generated/ScifiKitbashTid33MapImageMatches.csv`
- `generated/PptxLabelKitMatchSuggestions.csv`
- `generated/PptxLabelKitMatchReview.html`

The CSV/HTML files above are useful review artifacts, but they are not canonical docs.

## Documentation Rules

- Keep `README.md` short and operational.
- Keep current status in `docs/CurrentStatus.md`.
- Keep route inventory in `docs/API.md`, not in the README.
- Keep table/schema summaries in `docs/DataModel.md`; detailed truth remains `backend/schema.sql`.
- Keep speculative future entities out of implementation docs until they land in schema plus migrations.
