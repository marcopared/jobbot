"""Deterministic HTML resume template (EPIC 7)."""

from core.resumes.layout_types import LayoutPlan
from core.resumes.payload_types import ResumePayloadV2, ResumeSection


TEMPLATE_VERSION = "v1"


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _find_section(payload: ResumePayloadV2, section_id: str) -> ResumeSection:
    for section in payload.sections:
        if section.id == section_id:
            return section
    raise KeyError(f"Missing payload section: {section_id}")


def _render_section_body(section: ResumeSection) -> str:
    if section.kind == "summary":
        return f'<div class="summary">{_escape_html(section.body).replace("\n", "<br>")}</div>'
    if section.kind == "skills":
        skills_html = ", ".join(_escape_html(skill) for skill in section.lines)
        return f'<div class="skills">{skills_html}</div>'
    if section.kind == "experience":
        entries_html = []
        for entry in section.entries:
            company = _escape_html(entry.subheading)
            title = _escape_html(entry.heading)
            dates = _escape_html(entry.dates)
            bullets_html = "".join(
                f'<li>{_escape_html(bullet.text)}</li>' for bullet in entry.bullets
            )
            entries_html.append(
                f"""
            <div class="role">
                <div class="role-header">
                    <span class="role-title">{title}</span>
                    <span class="role-company">{company}</span>
                    <span class="role-dates">{dates}</span>
                </div>
                <ul class="role-bullets">{bullets_html}</ul>
            </div>
            """
            )
        return "\n".join(entries_html)
    if section.kind == "projects":
        entries_html = []
        for entry in section.entries:
            name = _escape_html(entry.heading)
            bullets_html = "".join(
                f'<li>{_escape_html(bullet.text)}</li>' for bullet in entry.bullets
            )
            entries_html.append(
                f"""
            <div class="project">
                <div class="project-name">{name}</div>
                <ul class="project-bullets">{bullets_html}</ul>
            </div>
            """
            )
        return "\n".join(entries_html)
    if section.kind == "education":
        lines_html = "".join(
            f'<div class="edu-line">{_escape_html(line)}</div>' for line in section.lines
        )
        return f'<div class="education">{lines_html}</div>'
    raise ValueError(f"Unsupported section kind: {section.kind}")


def render_html(payload: ResumePayloadV2, layout_plan: LayoutPlan) -> str:
    """
    Render a deterministic HTML resume from structured data.
    """
    name = _escape_html(payload.contact.name)
    email = _escape_html(payload.contact.email)
    location = _escape_html(payload.contact.location)
    ordered_sections = sorted(layout_plan.sections, key=lambda section: section.order)
    rendered_sections = []
    for section_plan in ordered_sections:
        section = _find_section(payload, section_plan.section_id)
        rendered_sections.append(
            f"""
    <h2>{_escape_html(section_plan.title)}</h2>
    {_render_section_body(section)}
            """
        )
    body_sections = "\n".join(rendered_sections)

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume — {name}</title>
    <style>
        @page {{ size: letter; margin: 0.5in; }}
        body {{ font-family: Georgia, "Times New Roman", serif; font-size: 11pt; line-height: 1.35; margin: 0.5in; color: #222; }}
        h1 {{ font-size: 18pt; font-weight: bold; margin: 0 0 4px 0; }}
        .contact {{ font-size: 10pt; color: #444; margin-bottom: 12px; }}
        .contact span {{ margin-right: 12px; }}
        h2 {{ font-size: 12pt; font-weight: bold; margin: 12px 0 6px 0; border-bottom: 1px solid #ccc; padding-bottom: 2px; }}
        .summary {{ margin-bottom: 12px; }}
        .skills {{ margin-bottom: 12px; }}
        .role {{ margin-bottom: 10px; }}
        .role-header {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }}
        .role-title {{ font-weight: bold; }}
        .role-company {{ color: #444; }}
        .role-dates {{ margin-left: auto; color: #555; font-size: 10pt; }}
        .role-bullets, .project-bullets {{ margin: 4px 0 0 16px; padding: 0; }}
        .role-bullets li, .project-bullets li {{ margin-bottom: 3px; }}
        .project {{ margin-bottom: 8px; }}
        .project-name {{ font-weight: bold; margin-bottom: 2px; }}
        .edu-line {{ margin-bottom: 2px; }}
    </style>
</head>
<body>
    <h1>{name}</h1>
    <div class="contact">
        <span>{email}</span>
        <span>{location}</span>
    </div>

    {body_sections}
</body>
</html>
"""
    return html.strip()
