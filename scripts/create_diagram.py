"""Render FreightLens architecture as matching PNG and editable SVG assets."""

from html import escape
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 2080, 1850
PAPER, WHITE, INK = "#f5f4f0", "#ffffff", "#252b2a"
MUTED, LINE, RUST = "#69706b", "#dedfd8", "#b94b2b"
GREEN, PALE_GREEN, PALE_RUST = "#41644b", "#eef4eb", "#faf0e9"


def font(size, bold=False):
    """Use installed Windows/Linux fonts, then Pillow's bundled fallback."""
    names = (
        ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def main():
    output = ROOT / "docs" / "assets"
    output.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title description">',
        '<title id="title">FreightLens system architecture</title>',
        '<desc id="description">ECC guides development and audit, outside the runtime. A local '
        "FastAPI application extracts and validates document text, records evidence in SQLite, "
        "and requires employee approval before JSON export. Findings or outdated policy block "
        "approval and export. A small Gemini public-PDF evaluation is recorded; "
        "Kimi is not live verified.</desc>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{PAPER}"/>',
    ]

    def rect(x, y, w, h, fill=WHITE, stroke=LINE, radius=8):
        draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=fill, outline=stroke)
        svg.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}"/>'
        )

    def text(x, y, value, size=21, color=INK, bold=False):
        loaded = font(size, bold)
        draw.text((x, y), value, font=loaded, fill=color, anchor="lt")
        svg.append(
            f'<text x="{x}" y="{y}" dominant-baseline="text-before-edge" '
            f'font-family="Segoe UI,DejaVu Sans,Arial,sans-serif" font-size="{size}" '
            f'font-weight="{650 if bold else 400}" fill="{color}">{escape(value)}</text>'
        )

    def arrow(points, color=MUTED, dashed=False, bidirectional=False):
        # Dashed paths denote optional external transport, never a second agent loop.
        if dashed:
            for start, end in zip(points, points[1:], strict=False):
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = hypot(dx, dy)
                for offset in range(0, int(length), 15):
                    stop = min(offset + 8, length)
                    draw.line(
                        [
                            (start[0] + dx * offset / length, start[1] + dy * offset / length),
                            (start[0] + dx * stop / length, start[1] + dy * stop / length),
                        ],
                        fill=color,
                        width=2,
                    )
        else:
            draw.line(points, fill=color, width=2, joint="curve")
        x, y = points[-1]
        px, py = points[-2]
        distance = hypot(x - px, y - py)
        ux, uy = (x - px) / distance, (y - py) / distance
        head = [
            (x, y),
            (x - 11 * ux - 6 * uy, y - 11 * uy + 6 * ux),
            (x - 11 * ux + 6 * uy, y - 11 * uy - 6 * ux),
        ]
        draw.polygon(head, fill=color)
        dash = ' stroke-dasharray="8 7"' if dashed else ""
        svg.append(
            f'<polyline points="{" ".join(f"{a},{b}" for a, b in points)}" '
            f'fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        )
        svg.append(f'<polygon points="{" ".join(f"{a},{b}" for a, b in head)}" fill="{color}"/>')
        if bidirectional:
            x, y = points[0]
            px, py = points[1]
            distance = hypot(x - px, y - py)
            ux, uy = (x - px) / distance, (y - py) / distance
            head = [
                (x, y),
                (x - 11 * ux - 6 * uy, y - 11 * uy + 6 * ux),
                (x - 11 * ux + 6 * uy, y - 11 * uy - 6 * ux),
            ]
            draw.polygon(head, fill=color)
            svg.append(
                f'<polygon points="{" ".join(f"{a},{b}" for a, b in head)}" fill="{color}"/>'
            )

    def card(x, y, number, title, lines, width=400, fill=WHITE, accent=RUST):
        rect(x, y, width, 160, fill)
        text(x + 20, y + 17, number, 16, accent, True)
        text(x + 20, y + 46, title, 25, INK, True)
        for index, line in enumerate(lines):
            if draw.textlength(line, font=font(19)) > width - 40:
                raise ValueError(f"Architecture line exceeds its card: {line}")
            text(x + 20, y + 84 + index * 24, line, 19, MUTED)

    text(64, 43, "FREIGHTLENS  /  SYSTEM ARCHITECTURE", 19, RUST, True)
    text(64, 83, "A clear path from paperwork to approval.", 50, INK, True)
    text(
        64,
        148,
        "Local portfolio prototype · One modular Python application · Human decisions",
        24,
        MUTED,
    )

    # Development specialists are explicitly outside the deployed application.
    rect(64, 210, 1952, 197, "#eeede6")
    text(90, 232, "ECC DEVELOPMENT & AUDIT WORKFLOW", 17, RUST, True)
    text(90, 264, "Architecture reviewer", 25, INK, True)
    text(90, 304, "Module boundaries, contracts, system design", 21, MUTED)
    text(755, 264, "Python / provider reviewer", 25, INK, True)
    text(755, 304, "Grounding, error paths, regression tests", 21, MUTED)
    text(1405, 264, "Security reviewer", 25, INK, True)
    text(1405, 304, "Upload boundary, data handling, approval gates", 21, MUTED)
    text(
        90,
        359,
        "Development guidance and review roles only. "
        "ECC is not a runtime dependency or an in-app agent team.",
        21,
        MUTED,
    )

    rect(64, 457, 1480, 1080, "#efeee8")
    text(90, 480, "LOCAL RUNTIME", 18, RUST, True)
    text(302, 480, "Browser + single FastAPI modular application + SQLite", 21, MUTED)

    card(
        110,
        550,
        "01 / BROWSER",
        "Employee workbench",
        [
            "Rate confirmation, invoice, POD",
            "Upload PDF / UTF-8 text packets",
            "Review values, source quotes, notes",
        ],
    )
    card(
        590,
        550,
        "02 / API BOUNDARY",
        "Bounded local requests",
        [
            "ASGI streamed-body size limit",
            "Host + Origin checks; typed routes",
            "api.py / middleware.py",
        ],
    )
    card(
        1070,
        550,
        "03 / APPLICATION SERVICE",
        "Versioned packet workflow",
        [
            "Validate inputs; fingerprint packet",
            "Reuse same provider / model / policy",
            "service.py / versions.py",
        ],
    )
    card(
        1070,
        790,
        "04 / INGESTION",
        "Numbered page text",
        [
            "Bound file size, pages, text length",
            "Reject unreadable or encrypted input",
            "ingestion.py · OCR not included",
        ],
    )
    card(
        590,
        790,
        "05 / EXTRACTION ADAPTER",
        "One provider per review",
        [
            "Demo parser: offline mode",
            "Gemini / Kimi: hosted APIs",
            "extraction.py · no model tools",
        ],
    )
    card(
        110,
        790,
        "06 / OUTPUT CONTRACT",
        "Schema + source evidence",
        [
            "Pydantic validates provider output",
            "Signed money + whole-token support",
            "Cited quote must exist on the page",
        ],
    )
    card(
        110,
        1030,
        "07 / BUSINESS RULES",
        "Deterministic checks",
        [
            "Decimal amounts, currency, dates",
            "Required fields + cross-doc conflicts",
            "rules.py · warnings block approval",
        ],
    )
    card(
        590,
        1030,
        "08 / SQLITE PERSISTENCE",
        "Evidence & review history",
        [
            "Page text, fields, findings, notes",
            "Hashes + processing provenance",
            "repository.py · no original PDFs",
        ],
    )
    card(
        1070,
        1030,
        "09 / EMPLOYEE DECISION",
        "Explicit approval gate",
        [
            "Inspect findings and source evidence",
            "No findings + current policy required",
            "Employee name and note recorded",
        ],
        fill=PALE_GREEN,
        accent=GREEN,
    )
    card(
        1070,
        1270,
        "APPROVED PATH",
        "JSON export",
        [
            "Employee-approved record only",
            "Current processing policy required",
            "Download; no automatic delivery",
        ],
        fill=PALE_GREEN,
        accent=GREEN,
    )
    card(
        590,
        1270,
        "BLOCKED PATH",
        "Approval / export denied",
        [
            "Findings or outdated policy records",
            "Notes do not clear discrepancies",
            "Old records remain readable",
        ],
        fill=PALE_RUST,
    )
    card(
        110,
        1270,
        "RECOVERY",
        "Clarify or replace documents",
        [
            "Confirm currency / dates with evidence",
            "Or upload missing / corrected files",
            "Original fields + reason retained",
        ],
    )

    # Main path reads left-to-right, down, right-to-left, then down and forward.
    arrow([(510, 630), (590, 630)])
    arrow([(990, 630), (1070, 630)])
    arrow([(1270, 710), (1270, 790)])
    arrow([(1070, 870), (990, 870)])
    arrow([(590, 870), (510, 870)])
    arrow([(310, 950), (310, 1030)])
    arrow([(510, 1110), (590, 1110)])
    arrow([(990, 1110), (1070, 1110)])
    arrow([(1400, 1190), (1400, 1270)], GREEN)
    text(1413, 1220, "approve", 16, GREEN)
    arrow([(1210, 1190), (1210, 1225), (790, 1225), (790, 1270)], RUST)
    text(838, 1199, "findings / old policy", 17, RUST)
    arrow([(590, 1350), (510, 1350)], RUST)
    arrow([(110, 1350), (84, 1350), (84, 630), (110, 630)], RUST)
    text(
        110,
        1474,
        "Stored provenance: provider · model · pipeline · extraction · rules revision",
        21,
        MUTED,
    )

    # External transport is distinct from the local application and from future work.
    rect(1600, 457, 416, 213, "#eeede6")
    text(1620, 482, "OPTIONAL EXTERNAL BOUNDARY", 15, RUST, True)
    text(1620, 518, "Hosted extraction only", 24, INK, True)
    text(1620, 559, "Document text leaves the device", 19, MUTED)
    text(1620, 589, "when a hosted mode is selected.", 19, MUTED)
    text(1620, 626, "No silent fallback to demo mode.", 18, MUTED)
    card(
        1600,
        790,
        "ADAPTER IMPLEMENTED",
        "Gemini / Kimi APIs",
        [
            "Gemini: public-PDF evaluation",
            "Kimi: live testing pending",
            "No API key in code or diagrams",
        ],
        width=416,
        fill=PALE_RUST,
    )
    arrow(
        [(790, 950), (790, 992), (1808, 992), (1808, 950)],
        RUST,
        dashed=True,
        bidirectional=True,
    )
    text(1547, 1006, "request / validated response", 18, RUST)

    rect(1600, 1095, 416, 442, WHITE)
    text(1620, 1122, "NEXT MILESTONES", 17, MUTED, True)
    text(1620, 1161, "Future work only", 25, INK, True)
    for index, line in enumerate(
        [
            "01  Broader accuracy + scope tests",
            "02  OCR for scanned documents",
            "03  Authentication + worker jobs",
            "04  Approved business integrations",
        ]
    ):
        text(1620, 1223 + index * 54, line, 19, MUTED)
    text(1620, 1479, "Not part of the current runtime.", 18, MUTED)

    rect(64, 1590, 1952, 173, WHITE)
    text(90, 1615, "SCOPE & TRUST", 17, RUST, True)
    text(90, 1655, "AI extracts. Python validates. Employees approve.", 29, INK, True)
    text(
        90,
        1703,
        "No automatic emails or payments. "
        "No RAG, memory, autonomous agents, model tools or webhooks.",
        23,
        MUTED,
    )
    text(
        64,
        1804,
        "FreightLens · Current local prototype architecture · PNG + editable SVG + Mermaid source",
        19,
        MUTED,
    )
    text(1640, 1804, "Small live test; see evaluation", 18, MUTED)

    svg.append("</svg>")
    image.save(output / "architecture.png")
    (output / "architecture.svg").write_text("\n".join(svg), encoding="utf-8")
    print("Created docs/assets/architecture.png and architecture.svg")


if __name__ == "__main__":
    main()
