import html

from app.services.translation import OPTION_LABEL_RE

COPY_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" '
    'class="copy-icon" aria-hidden="true">'
    '<path fill-rule="evenodd" d="M7.5 3.75A3.75 3.75 0 0 1 11.25 0h7.5A3.75 3.75 0 0 1 22.5 3.75v7.5A3.75 3.75 0 0 1 18.75 15h-7.5A3.75 3.75 0 0 1 7.5 11.25v-7.5Zm6.75 0v7.5a3.75 3.75 0 0 1-3.75 3.75h-7.5A3.75 3.75 0 0 1 0 11.25v-7.5A3.75 3.75 0 0 1 3.75 0h7.5Zm-6 12.75A3.75 3.75 0 0 1 10.5 9h7.5a3.75 3.75 0 0 1 3.75 3.75v7.5A3.75 3.75 0 0 1 18.75 24h-7.5A3.75 3.75 0 0 1 7.5 20.25v-7.5Z" clip-rule="evenodd"/>'
    "</svg>"
)
CHECK_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" '
    'class="check-icon" aria-hidden="true" hidden>'
    '<path fill-rule="evenodd" d="M19.916 4.626a.75.75 0 0 1 .208 1.04l-9 13.5a.75.75 0 0 1-1.154.114l-6-6a.75.75 0 0 1 1.06-1.06l5.353 5.353 8.493-12.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/>'
    "</svg>"
)


def parse_translation_options(text: str) -> list[tuple[str, str]] | None:
    matches = list(OPTION_LABEL_RE.finditer(text))
    if not matches:
        return None

    options: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        label = match.group(1).strip()
        body_start = match.end(1)
        body_end = (
            matches[index + 1].start(1) if index + 1 < len(matches) else len(text)
        )
        body = text[body_start:body_end].strip()
        options.append((label, body))

    return options


def _copy_command_section(label: str, text: str) -> str:
    escaped_label = html.escape(label)
    escaped_text = html.escape(text)
    return (
        '<div class="copy-command-section">'
        '<div class="copy-command-header">'
        f'<span class="copy-command-label">{escaped_label}</span>'
        '<button type="button" class="btn-copy" title="คัดลอก" aria-label="คัดลอก">'
        f'<span class="sr-only">คัดลอก</span>{COPY_ICON}{CHECK_ICON}'
        "</button>"
        "</div>"
        f'<div class="copy-command-body"><code>{escaped_text}</code></div>'
        "</div>"
    )


def format_translation_content(text: str) -> str:
    options = parse_translation_options(text)
    if not options:
        return f'<span class="plain-text">{html.escape(text)}</span>'

    matches = list(OPTION_LABEL_RE.finditer(text))
    preamble = text[: matches[0].start(1)].strip()

    parts: list[str] = []
    if preamble:
        parts.append(f'<div class="option-preamble">{html.escape(preamble)}</div>')

    parts.append('<div class="translation-options">')
    for label, body in options:
        parts.append(_copy_command_section(label, body))
    parts.append("</div>")
    return "".join(parts)
