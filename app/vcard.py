"""Render a contact as a vCard 3.0 (RFC 2426) document."""

import re

from app.models import Address, Contact

# vCard TYPE parameter per address kind; "Other" has no standard type.
_ADR_TYPES = {"Home": ";TYPE=HOME", "Work": ";TYPE=WORK"}

_MAX_LINE = 75


def _escape(value: str) -> str:
    """Escape the characters vCard text values reserve."""
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
    parts = [line[:_MAX_LINE]]
    rest = line[_MAX_LINE:]
    step = _MAX_LINE - 1  # continuation lines lose one column to the leading space
    while rest:
        parts.append(" " + rest[:step])
        rest = rest[step:]
    return "\r\n".join(parts)


def _adr(address: Address) -> str:
    components = ";".join(
        _escape(part or "")
        for part in (address.street, address.city, address.state, address.postal_code, address.country)
    )
    # ADR is: po-box;extended;street;city;region;postal-code;country
    return f"ADR{_ADR_TYPES.get(address.type, '')}:;;{components}"


def build_vcard(contact: Contact) -> str:
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
    if contact.job_title:
        lines.append(f"TITLE:{_escape(contact.job_title)}")
    lines.extend(_adr(address) for address in contact.addresses)
    if contact.notes:
        lines.append(f"NOTE:{_escape(contact.notes)}")
    if contact.photo:
        # "data:image/png;base64,<payload>" — already validated on write.
        header, _, payload = contact.photo.partition(",")
        subtype = header.removeprefix("data:image/").split(";", 1)[0].upper()
        lines.append(f"PHOTO;ENCODING=b;TYPE={subtype}:{payload}")
    lines.append(f"REV:{contact.updated_at.strftime('%Y%m%dT%H%M%SZ')}")
    lines.append("END:VCARD")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def vcard_filename(contact: Contact) -> str:
    """A safe attachment filename like `Ada Lovelace.vcf`."""
    stem = re.sub(r"[^A-Za-z0-9 _-]", "", contact.full_name).strip() or f"contact-{contact.id}"
    return f"{stem}.vcf"
