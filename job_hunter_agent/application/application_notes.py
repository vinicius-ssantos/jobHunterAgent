from __future__ import annotations


def append_note(existing_notes: str, new_note: str) -> str:
    normalized_existing = existing_notes.strip()
    normalized_new = new_note.strip()
    if not normalized_existing:
        return normalized_new
    existing_lines = {line.strip() for line in normalized_existing.splitlines() if line.strip()}
    if normalized_new in existing_lines:
        return normalized_existing
    return f"{normalized_existing}\n{normalized_new}"
