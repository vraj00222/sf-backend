"""Render a contact as a vCard 3.0 (RFC 2426) document."""

import re

from app import trivia
from app.models import Address, Contact

QR_BYTE_BUDGET = 2953
"""Version-40, error-correction-level-L byte-mode QR capacity — the largest
code most phone cameras still scan comfortably. A roast vCard is trimmed to
fit here rather than erroring, so it always scans."""

# vCard TYPE parameter per address kind; "Other" has no standard type.
_ADR_TYPES = {"Home": ";TYPE=HOME", "Work": ";TYPE=WORK"}

_MAX_LINE = 75


def _escape(value: str) -> str:
    """Escape the characters vCard text values reserve."""
    # Normalise CR first: a bare \r left in a value is a raw line break that
    # lenient parsers read as the start of a new property.
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """Fold a long content line: continuation lines start with a space."""
    if len(line) <= _MAX_LINE:
        return line
    # ponytail: folds on characters, not octets; fine for ASCII-heavy values
    # (base64 photos), switch to byte-aware folding if non-ASCII names overflow.
    step = _MAX_LINE - 1  # continuation lines lose one column to the leading space
    parts = [line[:_MAX_LINE]]
    parts += [" " + line[i : i + step] for i in range(_MAX_LINE, len(line), step)]
    return "\r\n".join(parts)


def _adr(address: Address) -> str:
    components = ";".join(
        _escape(part or "")
        for part in (address.street, address.city, address.state, address.postal_code, address.country)
    )
    # ADR is: po-box;extended;street;city;region;postal-code;country
    return f"ADR{_ADR_TYPES.get(address.type, '')}:;;{components}"


def _base_lines(contact: Contact, title: str | None) -> list[str]:
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_escape(contact.last_name)};{_escape(contact.first_name)};;;",
        f"FN:{_escape(contact.full_name)}",
        f"EMAIL;TYPE=INTERNET:{_escape(contact.email)}",
    ]
    if contact.phone:
        lines.append(f"TEL;TYPE=VOICE:{_escape(contact.phone)}")
    if contact.company:
        lines.append(f"ORG:{_escape(contact.company)}")
    if title:
        lines.append(f"TITLE:{_escape(title)}")
    lines.extend(_adr(address) for address in contact.addresses)
    return lines


def _render(lines: list[str], note: str | None, photo: str | None, updated_at) -> str:
    rendered = list(lines)
    if note:
        rendered.append(f"NOTE:{_escape(note)}")
    if photo:
        # "data:image/png;base64,<payload>" — already validated on write.
        header, _, payload = photo.partition(",")
        subtype = header.removeprefix("data:image/").split(";", 1)[0].upper()
        rendered.append(f"PHOTO;ENCODING=b;TYPE={subtype}:{payload}")
    rendered.append(f"REV:{updated_at.strftime('%Y%m%dT%H%M%SZ')}")
    rendered.append("END:VCARD")
    return "\r\n".join(_fold(line) for line in rendered) + "\r\n"


def build_vcard(contact: Contact, *, roast: bool = False) -> str:
    if not roast:
        lines = _base_lines(contact, contact.job_title)
        return _render(lines, contact.notes, contact.photo, contact.updated_at)

    phone_lines, grade = trivia.phone_roast(contact.phone)
    address = contact.addresses[0] if contact.addresses else None
    roast_lines = [
        *phone_lines,
        trivia.address_trivia(
            address.city if address else None,
            address.state if address else None,
            address.country if address else None,
        ),
    ]

    title = f"{contact.job_title} · Roast Grade: {grade}" if contact.job_title else f"Roast Grade: {grade}"
    lines = _base_lines(contact, title)

    # No photo in roast mode: a downscaled avatar alone can exceed the whole QR
    # budget, and the roast text needs the room instead. Trim trivia lines,
    # least essential (last) first; `notes` has no length cap, so if trivia
    # alone doesn't get there, drop the pre-existing notes too — the roast is
    # the point of this endpoint.
    kept = list(roast_lines)
    existing_notes = contact.notes
    while True:
        header = f"CODE REVIEW: {contact.full_name}\nStatus: CHANGES REQUESTED · Grade: {grade}"
        body = "\n".join([header, "", *(f"✗ {line}" for line in kept)]) if kept else header
        note = f"{existing_notes}\n\n{body}" if existing_notes else body
        text = _render(lines, note, photo=None, updated_at=contact.updated_at)
        if len(text.encode()) <= QR_BYTE_BUDGET:
            return text
        if kept:
            kept.pop()
        elif existing_notes:
            existing_notes = None
        else:
            return text  # nothing left to trim — an oversized name/address, most likely


def vcard_filename(contact: Contact) -> str:
    """A safe attachment filename like `Ada Lovelace.vcf`."""
    stem = re.sub(r"[^A-Za-z0-9 _-]", "", contact.full_name).strip() or f"contact-{contact.id}"
    return f"{stem}.vcf"
