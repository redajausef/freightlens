# FreightLens interface design

FreightLens is a shipment-review workbench for repeated daily use. The current interface uses
cool neutral surfaces, a compact slate navigation rail and cobalt actions. Amber findings and
teal approvals remain distinct from navigation. System fonts and local SVG icons keep the app
fast and usable offline; no frontend framework or design dependency was added.

## Product contract

- The initial screen prioritizes the review queue, reference/carrier search and real status
  filters. Counts are scoped to the latest 100 saved packets, not business-wide analytics.
- New review opens a native dialog. Explicit document types, selected filenames, size limits,
  offline examples and provider state remain visible. Errors and progress stay inside the dialog.
- Selecting a shipment keeps a compact clickable queue beside the review on wide screens.
  Summary filters shrink to leave more document space. At narrower widths, detail gets the full
  workspace and a Back control preserves orientation.
- Findings come before document tabs. Extracted fields and source text sit side by side on
  desktop and stack on mobile. Selected fields, documents and shipments are visibly identified.
- The source pane is labeled Extracted text. Original PDFs are not retained, so it does not
  pretend to be a PDF preview or verify authenticity.
- Human approval remains explicit and blocked for findings or earlier-policy records.
  Approved records show an accurate confirmation and real JSON download.
- Unsaved notes are held per review in memory while the app stays open. They do not transfer
  between shipments, and saving a note keeps the selected source document/field.
- Pending uploads preserve their request snapshot: file controls and close are disabled, Escape
  explains the wait, and failure preserves selected files. The app does not claim cancellation.
- Target viewports:1440x1000,1024x900,390x844. Avoid page-level horizontal overflow, contain long
  filenames/quotes, preserve focus, provide clear labels and honor reduced motion.

## Reference observations

The design borrows interaction principles from official product documentation, without copying
assets or adding unrelated features:

- [Linear UI reset](https://linear.app/changelog/2024-03-20-new-linear-ui): clear hierarchy,
  density and contrast, restrained navigation and panels.
- [Linear Inbox](https://linear.app/docs/inbox): keep list context while working on a selected item.
- [Vercel Geist tables](https://vercel.com/geist/table): semantic rows, tabular numerals, honest
  missing values and explicit empty states.

A public Linear page was opened locally, but its remote screenshot assets did not render.
Reference evidence is the official written guidance; no external screenshot was copied into the app.

## Concrete changes

| Area | Previous interface | Current interface |
|---|---|---|
| Workflow | Permanent upload column; review below queue | Queue first, focused upload dialog, queue/detail workspace |
| Appearance | Warm rust/olive, editorial separators | Cool neutral canvas, slate rail, cobalt selection/action |
| Document space | Long stacked sections | Compact focus filters and paired fields/source panes |
| Source inspection | Source page text hidden by default | Supporting quote and open, bounded page text |
| Files | Native input/button text only | Named file controls with clear selected filenames |
| Recovery | Global error could be outside modal focus | Local errors/progress, files retained, direct retry |
| Notes | Discarded when changing shipment | Per-review memory drafts; submitted text cleared only if unchanged |
| Save orientation | Source selection reset | Selected document and field preserved |
| Keyboard | Basic focus treatment | Skip link, search shortcut, explicit modal cycling, Escape and focus return |
| Approval | Clean wording also shown after approval | Accurate approved/blocked/earlier-policy feedback |

## ECC review and ownership

ECC frontend-design-direction, make-interfaces-feel-better, frontend-a11y and team orchestration
provided the design contract, polish criteria, state requirements and review structure. The
workflow reviewer supplied read-only recommendations. Accessibility review caught live regions
inside a busy ancestor, pending-edit note loss, and file changes during an in-flight upload;
Codex fixed these and verified them in the browser. Codex implemented/integrated
HTML, JavaScript and CSS. ECC is development guidance, not a runtime dependency.

## Rendered verification

Actual browser workflows cover PDF upload, missing/mismatched packets, notes, source navigation,
clean approval and a JSON download. Controlled browser routes exercise loading, startup 503/Retry,
provider failure, long content and pending upload behavior. Real earlier-policy records exercise
approval/export restrictions. Keyboard checks cover skip-link focus, modal Tab/Escape/focus return
and search. Computed text-color checks found no remaining contrast failures in the tested queue,
review and upload surfaces after fixes; decorative/disabled content is excluded. Primary actions
have 44px targets and secondary controls generally 40px or larger. Reduced motion is respected.

See [the current local evidence record](design-evidence/modern/evidence.json) and
[verification notes](verification.md). These checks are not an accessibility certification,
production-readiness claim or a live model accuracy evaluation.
