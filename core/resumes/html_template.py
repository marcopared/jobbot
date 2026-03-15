"""Deterministic HTML resume template (EPIC 7)."""

from dataclasses import dataclass


@dataclass
class RenderedResumeData:
    """Data structure for template injection."""

    contact_name: str
    contact_email: str
    contact_location: str
    summary: str
    skills: list[str]
    roles: list[dict]  # [{company, title, dates, bullets}]
    projects: list[dict]  # [{name, bullets}]
    education: list[dict]  # [{school, degree, year}]


TEMPLATE_VERSION = "v1"


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_html(data: RenderedResumeData) -> str:
    """
    Render a deterministic HTML resume from structured data.
    """
    name = _escape_html(data.contact_name)
    email = _escape_html(data.contact_email)
    location = _escape_html(data.contact_location)
    summary = _escape_html(data.summary).replace("\n", "<br>")

    skills_html = ", ".join(_escape_html(s) for s in data.skills)

    roles_html_parts = []
    for r in data.roles:
        company = _escape_html(r.get("company", ""))
        title = _escape_html(r.get("title", ""))
        dates = _escape_html(r.get("dates", ""))
        bullets = r.get("bullets", [])
        bullets_html = "".join(
            f'<li>{_escape_html(b)}</li>' for b in bullets
        )
        roles_html_parts.append(
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
    roles_section = "\n".join(roles_html_parts) if roles_html_parts else ""

    projects_html_parts = []
    for p in data.projects:
        name_ = _escape_html(p.get("name", ""))
        bullets = p.get("bullets", [])
        bullets_html = "".join(
            f'<li>{_escape_html(b)}</li>' for b in bullets
        )
        projects_html_parts.append(
            f"""
            <div class="project">
                <div class="project-name">{name_}</div>
                <ul class="project-bullets">{bullets_html}</ul>
            </div>
            """
        )
    projects_section = "\n".join(projects_html_parts) if projects_html_parts else ""

    education_html_parts = []
    for e in data.education:
        school = _escape_html(e.get("school", ""))
        degree = _escape_html(e.get("degree", ""))
        year = _escape_html(e.get("year", ""))
        education_html_parts.append(
            f'<div class="edu-line">{degree} — {school} ({year})</div>'
        )
    education_section = "\n".join(education_html_parts) if education_html_parts else ""

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

    <h2>Summary</h2>
    <div class="summary">{summary}</div>

    <h2>Skills</h2>
    <div class="skills">{skills_html}</div>

    <h2>Experience</h2>
    {roles_section}

    <h2>Projects</h2>
    {projects_section}

    <h2>Education</h2>
    <div class="education">{education_section}</div>
</body>
</html>
"""
    return html.strip()
