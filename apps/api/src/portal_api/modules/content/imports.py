"""Structured content import (roadmap P06.S2.T1/T2; IMPORT-01). See `docs/content-import.md` for the formats.

A batch is uploaded, validated in full and stored as a **preview** (dry run): per-row action (create, update,
unchanged, skip or error), row-level errors and warnings, and counts. Nothing touches the catalogue until the batch is
**committed**. Commit re-validates every row against the current database and writes all of its rows in one
transaction (the documented atomic boundary), or none. Every imported row becomes or updates a **draft** that goes
through the normal review, rights and publication gates; an import never submits, approves or publishes.

Idempotency: each row carries the author's stable `external_id`, unique per kind. Re-importing the same file finds
every row unchanged and writes nothing; a changed row updates the item's working draft (never a version in review or
published, which is skipped with a note to revise it in the studio). Committing a batch twice is refused; two batches
racing for the same new external ID cannot both create it (unique index), and the loser is told to preview again.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
import zlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET
from xml.parsers import expat

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, NotFound, TooLarge, TooMany, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import assets, blocks, kinds, workflow
from portal_api.modules.content.models import (
    Availability,
    ContentImportBatch,
    ContentImportRow,
    ContentItem,
    ContentVersion,
    ItemState,
    VersionStatus,
)
from portal_api.modules.curriculum.models import BookEdition, Chapter, Subject, Topic
from portal_api.modules.identity.deps import Principal
from portal_api.modules.identity.permissions import Permission, permissions_for

SCHEMA_VERSION = 1
IMPORT_KINDS = ("mcq", "lesson", "written", "storyboard", "rubric", "passage")
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 2000
MAX_DEPTH = 40  # rich blocks nest a few levels; anything deeper is hostile or broken (IMPORT-ABUSE-01)
PREVIEWS_PER_HOUR = 30  # per author: each preview validates every row against the catalogue (provisional)
PREVIEW_TTL = timedelta(hours=24)
EXTERNAL_ID_MAX = 120
CSV_COLUMNS = (
    "external_id",
    "chapter",
    "topic",
    "title",
    "stem",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct",
    "explanation",
    "difficulty",
    "estimated_seconds",
    "cognitive_demand",
    "source_document_id",
    "pdf_from",
    "pdf_to",
    "family",  # IMPORT-REFS-01: an existing question (external_id or ID) this one is a variant of
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Limits:
    """How much one file may hold. Previews in a request use the defaults; the bulk worker (IMPORT-BULK-01) more."""

    max_bytes: int
    max_rows: int
    max_part: int  # one unpacked part of a workbook

    @staticmethod
    def request() -> Limits:  # read at call time, so the module constants stay the single source
        return Limits(MAX_BYTES, MAX_ROWS, XLSX_MAX_PART)


def _too_many(limits: Limits) -> TooLarge:
    return TooLarge(f"A batch can have at most {limits.max_rows:,} rows; split the file.")


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ------------------------------------------------------------------ decoding
def _decode(data: bytes, limits: Limits) -> str:
    if len(data) > limits.max_bytes:
        raise TooLarge(f"Import files can be at most {limits.max_bytes // (1024 * 1024)} MB.")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Unprocessable("The file must be UTF-8 encoded.", code_reason="ENCODING") from None
    if "\x00" in text:  # Postgres text can't hold NUL; reject it here, not as a server error on save
        raise Unprocessable("The file contains a NUL character, which isn't allowed in text.", code_reason="ENCODING")
    return text


def _check_shape(doc: Any) -> None:
    """Iteratively (no recursion) bound nesting depth and reject NUL characters decoded from JSON escapes."""
    stack: list[tuple[Any, int]] = [(doc, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise Unprocessable(f"The file nests deeper than {MAX_DEPTH} levels.", code_reason="JSON")
        if isinstance(node, dict):
            stack.extend((v, depth + 1) for v in node.values())
            stack.extend((k, depth) for k in node)
        elif isinstance(node, list):
            stack.extend((v, depth + 1) for v in node)
        elif isinstance(node, str) and "\x00" in node:
            raise Unprocessable(
                "The file contains a NUL character, which isn't allowed in text.", code_reason="ENCODING"
            )


def _para(text: str) -> list[dict[str, Any]]:
    return [{"type": "paragraph", "text": text.strip()}] if text.strip() else []


def _csv_rows(text: str, limits: Limits) -> tuple[str, list[dict[str, Any]]]:
    """The MCQ CSV template (plain paragraphs). Rich blocks, formulas and images need the JSON format."""
    reader = csv.DictReader(io.StringIO(text))
    try:
        return _template_rows(reader.fieldnames or [], reader, limits)
    except csv.Error as e:  # e.g. a field over the parser's size limit, or a broken quote
        raise Unprocessable(f"The CSV file can't be read: {e}.", code_reason="CSV") from None


def _template_rows(
    fieldnames: Iterable[str], records: Iterable[dict[str, Any]], limits: Limits
) -> tuple[str, list[dict[str, Any]]]:
    """The multiple-choice template's columns (CSV_COLUMNS), from a CSV file or the first sheet of a workbook."""
    header = [h.strip() for h in fieldnames]
    missing = [
        c for c in ("external_id", "chapter", "title", "stem", "option_a", "option_b", "correct") if c not in header
    ]
    if missing:
        raise Unprocessable(f"Missing columns: {', '.join(missing)}.", code_reason="CSV_HEADER")
    unknown = [h for h in header if h not in CSV_COLUMNS]
    if unknown:
        raise Unprocessable(f"Unknown columns: {', '.join(unknown)}.", code_reason="CSV_HEADER")
    repeated = sorted({h for h in header if header.count(h) > 1})
    if repeated:  # one value would silently replace the other
        raise Unprocessable(f"Repeated columns: {', '.join(repeated)}.", code_reason="CSV_HEADER")
    rows: list[dict[str, Any]] = []
    for raw in records:
        if len(rows) >= limits.max_rows:  # stop reading at the limit instead of parsing a flood of rows
            raise _too_many(limits)
        r = {k.strip(): (v or "").strip() for k, v in raw.items() if k}
        options = [
            {"id": f"o{i + 1}", "blocks": _para(r.get(col, ""))}
            for i, col in enumerate(("option_a", "option_b", "option_c", "option_d"))
            if r.get(col, "")
        ]
        letter = r.get("correct", "").upper()
        correct = f"o{'ABCD'.index(letter) + 1}" if len(letter) == 1 and letter in "ABCD" else letter
        metadata: dict[str, Any] = {}
        for key in ("difficulty", "cognitive_demand"):
            if r.get(key):
                metadata[key] = r[key]
        if r.get("estimated_seconds"):
            metadata["estimated_seconds"] = (
                int(r["estimated_seconds"]) if r["estimated_seconds"].isdigit() else r["estimated_seconds"]
            )
        refs: list[Any] = []
        if r.get("source_document_id"):
            refs.append(
                {
                    "source_document_id": r["source_document_id"],
                    "pdf_from": int(r["pdf_from"]) if r.get("pdf_from", "").isdigit() else r.get("pdf_from"),
                    "pdf_to": int(r["pdf_to"]) if r.get("pdf_to", "").isdigit() else r.get("pdf_to"),
                }
            )
        rows.append(
            {
                "external_id": r.get("external_id", ""),
                "chapter": r.get("chapter", ""),
                "topic": r.get("topic") or None,
                "title": r.get("title", ""),
                "body": {
                    "stem": _para(r.get("stem", "")),
                    "options": options,
                    "correct_option_id": correct,
                    "explanation": {"correct": _para(r.get("explanation", ""))},
                    "metadata": metadata,
                },
                "source_refs": refs,
                **({"family": r["family"]} if r.get("family") else {}),
            }
        )
    return "mcq", rows


def _json_rows(text: str) -> tuple[str, list[dict[str, Any]]]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise Unprocessable(f"The file is not valid JSON (line {e.lineno}).", code_reason="JSON") from None
    except RecursionError:
        raise Unprocessable(f"The file nests deeper than {MAX_DEPTH} levels.", code_reason="JSON") from None
    _check_shape(doc)
    if not isinstance(doc, dict):
        raise Unprocessable("The file must be a JSON object with schema_version, kind and items.", code_reason="JSON")
    if doc.get("schema_version") != SCHEMA_VERSION:
        raise Unprocessable(
            f"Unsupported schema_version; this portal reads version {SCHEMA_VERSION}.", code_reason="SCHEMA_VERSION"
        )
    kind = doc.get("kind")
    if kind not in IMPORT_KINDS:
        raise Unprocessable(f"kind must be one of: {', '.join(IMPORT_KINDS)}.", code_reason="KIND")
    items = doc.get("items")
    if not isinstance(items, list):
        raise Unprocessable("items must be a list.", code_reason="JSON")
    return str(kind), [i if isinstance(i, dict) else {"_invalid": True} for i in items]


# ------------------------------------------------------------------ Excel workbooks (IMPORT-XLSX-01)
# Read with the standard library, never evaluated: the first worksheet's cached cell values only. Every part is read
# with a hard size cap (a small zip can inflate enormously). The XML parser itself refuses any DOCTYPE or entity
# declaration, after decoding, so the rule holds in every encoding (OCT14-06); nothing is ever expanded or fetched.
# A damaged, encrypted or unsupported member is a validation error like any other unreadable file (OCT14-03).
XLSX_MAX_PART = 25 * 1024 * 1024
XLSX_MAX_PARTS = 500
XLSX_MAX_COLUMNS = 64
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"^([A-Z]{1,3})\d+$")
# What reading one member of a zip can raise besides a missing name: a CRC mismatch or damaged directory
# (BadZipFile), a damaged deflate stream (zlib.error), a truncated member (EOFError), an unsupported compression
# method (NotImplementedError) or an encrypted member (RuntimeError, "password required").
ZIP_MEMBER_ERRORS: tuple[type[BaseException], ...] = (
    zipfile.BadZipFile,
    zlib.error,
    EOFError,
    NotImplementedError,
    RuntimeError,
)


class _Declaration(Exception):
    pass


def _qname(name: str) -> str:
    return "{" + name if "}" in name else name  # expat gives "uri}local"; ElementTree uses "{uri}local"


def parse_xml(data: bytes) -> ET.Element:
    """Parse one workbook part, refusing any DOCTYPE or entity declaration. expat reports a declaration after it has
    decoded the document, so the refusal doesn't depend on UTF-8, UTF-16 or any other encoding."""

    def refuse(*_: object) -> None:
        raise _Declaration

    def refuse_external(*_: object) -> int:
        raise _Declaration

    builder = ET.TreeBuilder()
    parser = expat.ParserCreate(namespace_separator="}")
    parser.StartDoctypeDeclHandler = refuse
    parser.EntityDeclHandler = refuse
    parser.UnparsedEntityDeclHandler = refuse
    parser.NotationDeclHandler = refuse
    parser.ExternalEntityRefHandler = refuse_external
    parser.buffer_text = True
    parser.StartElementHandler = lambda tag, attrs: builder.start(_qname(tag), {_qname(k): v for k, v in attrs.items()})
    parser.EndElementHandler = lambda tag: builder.end(_qname(tag))
    parser.CharacterDataHandler = builder.data
    parser.Parse(data, True)
    return builder.close()


def _unreadable(why: str) -> Unprocessable:
    return Unprocessable(
        f"The workbook can't be read: {why}. Save it as .xlsx (Excel Workbook), or as CSV UTF-8.", code_reason="XLSX"
    )


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # transitional and strict workbooks use different namespaces; names are the same


def _optional(z: zipfile.ZipFile, name: str, cap: int) -> ET.Element | None:
    try:
        with z.open(name) as f:
            data = f.read(cap + 1)
    except KeyError:
        return None
    except ZIP_MEMBER_ERRORS:
        raise _unreadable(f"{name} is damaged, encrypted or compressed in a way that can't be read") from None
    if len(data) > cap:
        raise TooLarge(f"A part of the workbook ({name}) is larger than {cap // (1024 * 1024)} MB unpacked.")
    try:
        return parse_xml(data)
    except _Declaration:
        raise _unreadable("it declares a DOCTYPE or entities, which workbooks never need") from None
    except expat.ExpatError:
        raise _unreadable(f"{name} is not valid XML") from None


def _required(z: zipfile.ZipFile, name: str, cap: int) -> ET.Element:
    el = _optional(z, name, cap)
    if el is None:
        raise _unreadable(f"{name} is missing")
    return el


def _targets(z: zipfile.ZipFile, rels: str, base: str, *, kind: str | None = None) -> dict[str, str]:
    """Relationship ID -> part path (internal targets only; `kind` keeps only that relationship type)."""
    root = _optional(z, rels, XLSX_MAX_PART)  # relationship parts are tiny
    out: dict[str, str] = {}
    for r in [] if root is None else list(root):
        target = r.get("Target") or ""
        if r.get("TargetMode") == "External" or (kind and not (r.get("Type") or "").endswith("/" + kind)):
            continue
        out[r.get("Id") or ""] = target.lstrip("/") if target.startswith("/") else base + target
    return out


def _text(el: ET.Element) -> str:
    """A string item's text: plain `t`, or the `t` of each rich-text run; phonetic guides (`rPh`) are not text."""
    parts: list[str] = []
    for child in el:
        name = _local(child.tag)
        if name == "t":
            parts.append(child.text or "")
        elif name == "r":
            parts.extend(t.text or "" for t in child if _local(t.tag) == "t")
    return "".join(parts)


def _column(ref: str | None, fallback: int) -> int:
    m = _CELL_REF.match(ref or "")
    if not m:
        return fallback
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_table(data: bytes, limits: Limits | None = None) -> tuple[list[str], list[dict[str, str]]]:
    """The first worksheet as headings and rows (each row a dict by heading). Blank rows are skipped."""
    limits = limits or Limits.request()
    if len(data) > limits.max_bytes:
        raise TooLarge(f"Import files can be at most {limits.max_bytes // (1024 * 1024)} MB.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, EOFError, ValueError, NotImplementedError):
        raise _unreadable("it isn't an .xlsx file (an old .xls or a password-protected file can't be read)") from None
    with z:
        if len(z.infolist()) > XLSX_MAX_PARTS:
            raise _unreadable("it has too many parts")
        book_path = next(iter(_targets(z, "_rels/.rels", "", kind="officeDocument").values()), "xl/workbook.xml")
        base = book_path.rsplit("/", 1)[0] + "/" if "/" in book_path else ""
        book = _required(z, book_path, XLSX_MAX_PART)
        sheets = [el for el in book.iter() if _local(el.tag) == "sheet"]
        if not sheets:
            raise _unreadable("it has no worksheet")
        rid = next((v for k, v in sheets[0].attrib.items() if _local(k) == "id"), "")
        sheet_path = _targets(z, f"{base}_rels/{book_path.rsplit('/', 1)[-1]}.rels", base).get(rid)
        if not sheet_path:
            raise _unreadable("its first worksheet can't be found")
        sst = _optional(z, f"{base}sharedStrings.xml", limits.max_part)
        shared = [] if sst is None else [_text(si) for si in sst if _local(si.tag) == "si"]
        return _sheet_rows(_required(z, sheet_path, limits.max_part), shared, limits)


def _sheet_rows(sheet: ET.Element, shared: list[str], limits: Limits) -> tuple[list[str], list[dict[str, str]]]:
    def cells(row: ET.Element) -> list[str]:
        values: dict[int, str] = {}
        for i, c in enumerate(el for el in row if _local(el.tag) == "c"):
            col = _column(c.get("r"), i)
            if col >= XLSX_MAX_COLUMNS:
                raise _unreadable(f"it uses more than {XLSX_MAX_COLUMNS} columns")
            kind = c.get("t")
            v = next((el.text or "" for el in c if _local(el.tag) == "v"), "")
            if kind == "s":
                try:
                    v = shared[int(v)]
                except (ValueError, IndexError):
                    raise _unreadable("a cell points at a missing shared string") from None
            elif kind == "inlineStr":
                v = next((_text(el) for el in c if _local(el.tag) == "is"), "")
            values[col] = v.strip()
        width = max(values, default=-1) + 1
        return [values.get(i, "") for i in range(width)]

    rows: Iterator[list[str]] = (
        cells(r) for data in sheet if _local(data.tag) == "sheetData" for r in data if _local(r.tag) == "row"
    )
    nonblank = (r for r in rows if any(r))
    header = next(nonblank, [])
    records: list[dict[str, str]] = []
    for r in nonblank:
        if len(records) >= limits.max_rows:  # stop at the limit instead of building a flood of rows
            raise _too_many(limits)
        for i, v in enumerate(r):
            if v and (i >= len(header) or not header[i]):
                raise Unprocessable(
                    f"Column {i + 1} has values but no heading; add its heading or delete the column.",
                    code_reason="CSV_HEADER",
                )
        records.append({h: (r[i] if i < len(r) else "") for i, h in enumerate(header) if h})
    return [h for h in header if h], records


def xlsx_template(headings: Iterable[str]) -> bytes:
    """A headings-only workbook: every column formatted as text (so IDs keep leading zeros), the heading row frozen."""
    names = list(headings)

    def col(i: int) -> str:
        s, i = "", i + 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    cells = "".join(f'<c r="{col(i)}1" s="2" t="inlineStr"><is><t>{h}</t></is></c>' for i, h in enumerate(names))
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_DOC_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>'
        ),
        "xl/workbook.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{_MAIN}" xmlns:r="{_DOC_REL}">'
            '<sheets><sheet name="Questions" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_DOC_REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId2" Type="{_DOC_REL}/styles" Target="styles.xml"/></Relationships>'
        ),
        "xl/styles.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="{_MAIN}">'
            '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
            '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
            '<fills count="2"><fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="49" fontId="1" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1"/>'
            "</cellXfs>"
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{_MAIN}">'
            '<sheetViews><sheetView workbookViewId="0">'
            '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            f'<cols><col min="1" max="{len(names)}" width="22" style="1" customWidth="1"/></cols>'
            f'<sheetData><row r="1">{cells}</row></sheetData></worksheet>'
        ),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(name, xml)
    return buf.getvalue()


def parse_file(data: bytes, fmt: str, limits: Limits | None = None) -> tuple[str, list[dict[str, Any]]]:
    limits = limits or Limits.request()
    if fmt == "xlsx":
        header, records = xlsx_table(data, limits)
        for record in records:
            if any("\x00" in v for v in record.values()):
                raise Unprocessable(
                    "The file contains a NUL character, which isn't allowed in text.", code_reason="ENCODING"
                )
        kind, rows = _template_rows(header, records, limits)
    else:
        text = _decode(data, limits)
        kind, rows = _csv_rows(text, limits) if fmt == "csv" else _json_rows(text)
    if not rows:
        raise Unprocessable("The file has no rows.", code_reason="EMPTY")
    if len(rows) > limits.max_rows:
        raise _too_many(limits)
    return kind, rows


# ------------------------------------------------------------------ validation
def _chapter(db: Session, ref: str) -> Chapter | None:
    try:
        return db.get(Chapter, uuid.UUID(ref))
    except ValueError:
        return db.scalar(select(Chapter).where(Chapter.natural_key == ref))


def _topic(db: Session, ref: str, chapter: Chapter) -> Topic | None:
    try:
        t = db.get(Topic, uuid.UUID(ref))
    except ValueError:
        t = db.scalar(select(Topic).where(Topic.natural_key == ref))
    return t if t is not None and t.chapter_id == chapter.id and t.retired_at is None else None


def _ref(db: Session, kind: str, ref: object) -> ContentItem | None:
    """IMPORT-REFS-01: an existing item of this kind by its import external_id or its ID."""
    if not isinstance(ref, str) or not ref.strip():
        return None
    ref = ref.strip()
    try:
        item = db.get(ContentItem, uuid.UUID(ref))
    except ValueError:
        item = db.scalar(select(ContentItem).where(ContentItem.kind == kind, ContentItem.external_ref == ref))
    return item if item is not None and item.kind == kind else None


def _links(
    db: Session, kind: str, raw: dict[str, Any], chapter: Chapter, body: Any, ext: str | None
) -> tuple[dict[str, Any], Any, list[str]]:
    """IMPORT-REFS-01: references to other items. A rubric names its written question (and marks its current version);
    a question may name a variant family and a passage. Returns (payload additions, body, errors)."""
    extra: dict[str, Any] = {}
    errors: list[str] = []
    if kind == "rubric":
        q = _ref(db, "written", raw.get("question"))
        if q is None:
            errors.append("question: name an existing written question (its external_id or ID).")
        elif q.chapter_id != chapter.id:
            errors.append("question: the written question is in another chapter; a rubric lives with its question.")
        else:
            version = q.working_version_id or q.published_version_id
            if version is None:
                errors.append("question: the written question has no version to mark yet.")
            else:
                other = db.scalar(
                    select(ContentItem).where(
                        ContentItem.kind == "rubric",
                        ContentItem.parent_item_id == q.id,
                        ContentItem.external_ref.is_distinct_from(ext),
                    )
                )
                if other is not None:
                    errors.append("question: it already has a rubric; change that one in the studio.")
                extra = {"parent_item_id": str(q.id), "question_ref": str(raw.get("question")).strip()}
                if isinstance(body, dict):
                    body = {**body, "question_version_id": str(version)}
    if kind == "lesson":  # LESSON-VARIANTS-01 by import: a language variant of an existing lesson concept
        language = raw.get("language", "en")
        if language not in ("en", "ur", "roman_ur"):
            errors.append("language: use en, ur or roman_ur.")
        else:
            extra["language"] = language
        if raw.get("variant_of"):
            base = _ref(db, "lesson", raw.get("variant_of"))
            if base is None or base.chapter_id != chapter.id:
                errors.append("variant_of: name an existing lesson in the same chapter (its external_id or ID).")
            elif base.external_ref == ext:
                errors.append("variant_of: a lesson can't be a variant of itself.")
            else:
                extra["concept_id"] = str(base.concept_id or base.id)
                extra["variant_of_ref"] = str(raw["variant_of"]).strip()
                if base.topic_id is not None and raw.get("topic") is None:
                    extra["topic_id_from_base"] = str(base.topic_id)
    if kind == "mcq":
        if raw.get("family"):
            base = _ref(db, "mcq", raw.get("family"))
            if base is None or base.chapter_id != chapter.id:
                errors.append("family: name an existing question in the same chapter (its external_id or ID).")
            else:
                extra["family_id"] = str(base.family_id or base.id)
                extra["family_ref"] = str(raw["family"]).strip()
        if raw.get("passage"):
            passage = _ref(db, "passage", raw.get("passage"))
            if passage is None or passage.chapter_id is None:
                errors.append("passage: name an existing passage (its external_id or ID).")
            else:
                extra["passage_ref"] = str(raw["passage"]).strip()
                if isinstance(body, dict):
                    body = {**body, "passage_id": str(passage.id)}
    return extra, body, errors


def _validate_row(
    db: Session, who: Principal, kind: str, raw: dict[str, Any], scope_cache: dict[Any, bool]
) -> dict[str, Any]:
    """One row's action, errors, warnings and normalised payload. Writes nothing."""
    errors: list[str] = []
    warnings: list[str] = []
    ext = raw.get("external_id")
    if raw.get("_invalid"):
        return {"external_id": None, "action": "error", "errors": ["Each item must be a JSON object."], "warnings": []}
    if not isinstance(ext, str) or not ext.strip() or len(ext.strip()) > EXTERNAL_ID_MAX:
        errors.append(f"external_id is required (at most {EXTERNAL_ID_MAX} characters).")
        ext = None
    else:
        ext = ext.strip()
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 300:
        errors.append("title is required (at most 300 characters).")
    chapter = _chapter(db, str(raw.get("chapter") or ""))
    payload: dict[str, Any] = {}
    if chapter is None or chapter.retired_at is not None:
        errors.append("chapter: unknown or retired chapter (use its stable key or ID).")
    else:
        book = db.get(BookEdition, chapter.book_id)
        subject = db.get(Subject, book.subject_id) if book else None
        if book is None or subject is None or not subject.active:
            errors.append("chapter: outside the current academic scope.")
        else:
            key = (book.grade.number, subject.code)
            if key not in scope_cache:
                roles = workflow.roles_in_scope(db, who.user.id, *key)
                scope_cache[key] = Permission.draft_content in permissions_for(roles)
            if not scope_cache[key]:
                errors.append(f"You can't draft Class {key[0]} {key[1]} content.")
            topic_id = None
            if raw.get("topic"):
                topic = _topic(db, str(raw["topic"]), chapter)
                if topic is None:
                    errors.append("topic: not a current topic of this chapter.")
                else:
                    topic_id = str(topic.id)
            links, linked_body, link_errors = _links(db, kind, raw, chapter, raw.get("body"), ext)
            errors += link_errors
            body, body_errors, types = kinds.get(kind).parse_draft(linked_body)
            errors += [f"body: {e}" for e in body_errors]
            if body is not None:  # every diagram, model poster, frame or fallback must already be in the archive
                errors += [f"body: {e}" for e in assets.check_references(db, key[0], key[1], body)]
            s_err, s_warn, refs = workflow.check_sources(db, chapter, raw.get("source_refs", []))
            errors += s_err
            warnings += s_warn
            if not raw.get("source_refs"):
                warnings.append("No source page references yet; they are required before publication.")
            if body is not None:
                pub = kinds.get(kind).validate(body, True)
                warnings += [f"before publication: {e}" for e in pub.errors]
                payload = {
                    "chapter_id": str(chapter.id),
                    "topic_id": topic_id,
                    "title": title.strip() if isinstance(title, str) else "",
                    "body": body,
                    "block_types": types,
                    "source_refs": refs,
                    **links,
                }
    if errors:
        return {"external_id": ext, "action": "error", "errors": errors, "warnings": warnings}
    existing = db.scalar(select(ContentItem).where(ContentItem.kind == kind, ContentItem.external_ref == ext))
    digest = _hash(payload)
    if existing is None:
        action = "create"
    elif existing.state not in (ItemState.draft.value, ItemState.changes_requested.value):
        action = "skip"
        warnings.append(f"Already {existing.state.replace('_', ' ')}; start a revision in the studio to change it.")
    elif existing.import_hash == digest:
        action = "unchanged"
    elif str(existing.chapter_id) != payload["chapter_id"]:
        return {
            "external_id": ext,
            "action": "error",
            "errors": ["This external_id already belongs to another chapter; items don't move between chapters."],
            "warnings": warnings,
        }
    else:
        action = "update"
    return {
        "external_id": ext,
        "action": action,
        "errors": [],
        "warnings": warnings,
        "item_id": str(existing.id) if existing else None,
        "payload": payload,
        "payload_hash": digest,
    }


def preview(db: Session, who: Principal, data: bytes, *, fmt: str, filename: str) -> ContentImportBatch:
    if fmt not in ("json", "csv", "xlsx"):
        raise Unprocessable("Choose json, csv or xlsx.")
    kind, raw_rows = parse_file(data, fmt)
    recent = db.scalar(
        select(func.count())
        .select_from(ContentImportBatch)
        .where(
            ContentImportBatch.created_by == who.user.id,
            ContentImportBatch.created_at > func.now() - timedelta(hours=1),
        )
    )
    if (recent or 0) >= PREVIEWS_PER_HOUR:  # P18.S2.T2: validation is the expensive part of a preview
        raise TooMany(f"You've previewed {PREVIEWS_PER_HOUR} imports in the last hour. Please wait before the next.")
    scope_cache: dict[Any, bool] = {}
    results = [_validate_row(db, who, kind, r, scope_cache) for r in raw_rows]
    mark_duplicates(results)
    counts = count_actions(results)
    batch = ContentImportBatch(
        id=uuid.uuid4(),
        kind=kind,
        format=fmt,
        filename=filename[:200],
        sha256=hashlib.sha256(data).hexdigest(),
        schema_version=SCHEMA_VERSION,
        status="previewed",
        counts=counts,
        created_by=who.user.id,
        expires_at=_now() + PREVIEW_TTL,
        rows_total=len(results),
        rows_checked=len(results),
    )
    db.add(batch)
    db.flush()
    for n, r in enumerate(results, start=1):
        db.add(
            ContentImportRow(
                batch_id=batch.id,
                row_number=n,
                external_id=r.get("external_id"),
                action=r["action"],
                errors=r["errors"],
                warnings=r["warnings"],
                payload=r.get("payload") or {},
                payload_hash=r.get("payload_hash"),
                item_id=uuid.UUID(r["item_id"]) if r.get("item_id") else None,
            )
        )
    record(
        db,
        actor=who.user.id,
        action="content.import_previewed",
        target_type="content_import_batch",
        target_id=str(batch.id),
        details={"kind": kind, "format": fmt, "sha256": batch.sha256, "counts": counts},
    )
    db.commit()
    db.refresh(batch)
    return batch


def mark_duplicates(results: list[dict[str, Any]]) -> None:
    """Across the whole file: a repeated external_id is an error; the same question text twice is a warning."""
    seen: dict[str, int] = {}
    stems: dict[str, int] = {}
    for n, r in enumerate(results, start=1):
        ext = r.get("external_id")
        if ext and ext in seen:
            r["action"] = "error"
            r["errors"] = [*r["errors"], f"Duplicate external_id; first used on row {seen[ext]}."]
        elif ext:
            seen[ext] = n
        body = (r.get("payload") or {}).get("body") or {}
        stem = json.dumps(body.get("stem") or body.get("blocks") or [], sort_keys=True).lower()
        if stem not in ("[]", "") and r["action"] != "error":
            if stem in stems:
                r["warnings"] = [*r["warnings"], f"Same text as row {stems[stem]}; check this isn't a duplicate."]
            else:
                stems[stem] = n


def count_actions(results: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return counts


# ------------------------------------------------------------------ commit
def _own_batch(db: Session, who: Principal, batch_id: uuid.UUID, *, for_update: bool = False) -> ContentImportBatch:
    stmt = select(ContentImportBatch).where(ContentImportBatch.id == batch_id)
    if for_update:
        stmt = stmt.with_for_update()
    batch = db.scalar(stmt)
    if batch is None or batch.created_by != who.user.id:
        raise NotFound("Import not found.")
    return batch


def rows(db: Session, batch_id: uuid.UUID) -> list[ContentImportRow]:
    return list(
        db.scalars(
            select(ContentImportRow).where(ContentImportRow.batch_id == batch_id).order_by(ContentImportRow.row_number)
        )
    )


def get_batch(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    return _own_batch(db, who, batch_id)


def list_batches(db: Session, who: Principal) -> list[ContentImportBatch]:
    return list(
        db.scalars(
            select(ContentImportBatch)
            .where(ContentImportBatch.created_by == who.user.id)
            .order_by(ContentImportBatch.created_at.desc())
            .limit(50)
        )
    )


def discard(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    from portal_api.modules.content import bulk_imports

    batch = _own_batch(db, who, batch_id, for_update=True)
    if batch.status in ("validating", "committing"):
        raise Conflict("This import is being processed. Wait for it to finish, then discard it.")
    if batch.status not in ("previewed", "queued"):
        raise Conflict(f"This import is already {batch.status}.")
    key, batch.file_key = batch.file_key, None  # IMPORT-BULK-01: a queued upload goes once this has committed
    batch.status = "discarded"
    db.commit()
    bulk_imports.remove_upload(key)
    return batch


def check_committable(db: Session, batch: ContentImportBatch) -> list[ContentImportRow]:
    if batch.status != "previewed":
        raise Conflict(f"This import is already {batch.status}.")
    if batch.expires_at <= _now():
        raise Conflict("This preview is more than a day old. Upload the file again to preview it.")
    stored = rows(db, batch.id)
    if any(r.action == "error" for r in stored):
        raise Conflict("Fix the rows with errors and preview the file again; nothing was imported.")
    return stored


def commit(db: Session, who: Principal, batch_id: uuid.UUID) -> ContentImportBatch:
    from portal_api.modules.content import bulk_imports

    batch = _own_batch(db, who, batch_id, for_update=True)
    stored = check_committable(db, batch)
    if len(stored) > bulk_imports.SYNC_COMMIT_ROWS:  # IMPORT-BULK-01: a very large batch commits in the worker
        return bulk_imports.queue_commit(db, who, batch)
    apply_commit(db, who, batch, stored)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("Another import created some of these items at the same time; preview the file again.") from None
    db.refresh(batch)
    return batch


def apply_commit(db: Session, who: Principal, batch: ContentImportBatch, stored: list[ContentImportRow]) -> None:
    """Write every create/update row of a checked batch, without committing (the caller owns the transaction)."""
    scope_cache: dict[Any, bool] = {}
    written = {"created": 0, "updated": 0}
    for r in stored:
        if r.action not in ("create", "update"):
            continue
        # Re-check against the current database: another batch or editor may have changed things since the preview.
        fresh = _validate_row(db, who, batch.kind, _row_input(r), scope_cache)
        if fresh["action"] == "error":  # e.g. the author no longer holds a role for that class and subject
            db.rollback()
            why = (fresh["errors"] or ["it no longer passes the checks"])[0]
            raise Conflict(f"Row {r.row_number} ({r.external_id}) can no longer be imported: {why}", row=r.row_number)
        if fresh["action"] != r.action or fresh.get("payload_hash") != r.payload_hash:
            db.rollback()
            raise Conflict(
                f"Row {r.row_number} ({r.external_id}) changed since the preview; preview the file again.",
                row=r.row_number,
            )
        if r.action == "create":
            item_id = _create(db, who, batch, r)
            r.item_id = item_id
            written["created"] += 1
        else:
            _update(db, who, batch, r)
            written["updated"] += 1
    batch.status = "committed"
    batch.committed_at = _now()
    batch.counts = {**batch.counts, **{f"written_{k}": v for k, v in written.items()}}
    record(
        db,
        actor=who.user.id,
        action="content.import_committed",
        target_type="content_import_batch",
        target_id=str(batch.id),
        details={"kind": batch.kind, "sha256": batch.sha256, **written},
    )


def _row_input(r: ContentImportRow) -> dict[str, Any]:
    p = r.payload
    return {
        "external_id": r.external_id,
        "chapter": p["chapter_id"],
        "topic": p.get("topic_id"),
        "title": p["title"],
        "body": p["body"],
        "source_refs": p["source_refs"],
        **({"question": p["question_ref"]} if p.get("question_ref") else {}),
        **({"family": p["family_ref"]} if p.get("family_ref") else {}),
        **({"passage": p["passage_ref"]} if p.get("passage_ref") else {}),
        **({"language": p["language"]} if p.get("language") else {}),
        **({"variant_of": p["variant_of_ref"]} if p.get("variant_of_ref") else {}),
    }


def _apply_variant(item: ContentItem, p: dict[str, Any]) -> None:
    """LESSON-VARIANTS-01: an imported variant joins its base lesson's concept and topic; a human-authored one."""
    item.language = p.get("language") or "en"
    if p.get("concept_id"):
        item.concept_id = uuid.UUID(p["concept_id"])
        item.translation_origin = "human"
        if item.topic_id is None and p.get("topic_id_from_base"):
            item.topic_id = uuid.UUID(p["topic_id_from_base"])


def _create(db: Session, who: Principal, batch: ContentImportBatch, r: ContentImportRow) -> uuid.UUID:
    p = r.payload
    chapter = db.get(Chapter, uuid.UUID(p["chapter_id"]))
    assert chapter is not None
    book = db.get(BookEdition, chapter.book_id)
    assert book is not None
    subject = db.get(Subject, book.subject_id)
    assert subject is not None
    item = ContentItem(
        id=uuid.uuid4(),
        kind=batch.kind,
        chapter_id=chapter.id,
        topic_id=uuid.UUID(p["topic_id"]) if p.get("topic_id") else None,
        grade_number=book.grade.number,
        subject_code=subject.code,
        title=p["title"],
        state=ItemState.draft.value,
        availability=Availability.unpublished.value,
        created_by=who.user.id,
        external_ref=r.external_id,
        import_hash=r.payload_hash,
    )
    if batch.kind in ("mcq", "written"):
        item.family_id = uuid.UUID(p["family_id"]) if p.get("family_id") else item.id  # IMPORT-REFS-01: a variant
    if batch.kind == "rubric":
        item.parent_item_id = uuid.UUID(p["parent_item_id"])  # a rubric lives with its written question
    if batch.kind == "lesson":
        _apply_variant(item, p)
    version = ContentVersion(
        id=uuid.uuid4(),
        item_id=item.id,
        number=1,
        status=VersionStatus.draft.value,
        revision=1,
        content_schema_version=blocks.CONTENT_SCHEMA_VERSION,
        body=p["body"],
        block_types=p["block_types"],
        source_refs=p["source_refs"],
        created_by=who.user.id,
        contributors=[str(who.user.id)],
        updated_by=who.user.id,
    )
    db.add(item)
    db.flush()
    db.add(version)
    db.flush()
    item.working_version_id = version.id
    record(
        db,
        actor=who.user.id,
        action="content.imported",
        target_type="content_item",
        target_id=str(item.id),
        details={"batch": str(batch.id), "row": r.row_number, "external_id": r.external_id, "created": True},
    )
    return item.id


def _update(db: Session, who: Principal, batch: ContentImportBatch, r: ContentImportRow) -> None:
    item = workflow.get_item(db, r.item_id, for_update=True) if r.item_id else None
    if item is None or item.state not in (ItemState.draft.value, ItemState.changes_requested.value):
        raise Conflict(f"Row {r.row_number} ({r.external_id}) is no longer a draft; preview the file again.")
    p = r.payload
    version = db.get(ContentVersion, item.working_version_id)
    assert version is not None
    version.body = p["body"]
    version.block_types = p["block_types"]
    version.source_refs = p["source_refs"]
    version.revision += 1
    version.updated_by = who.user.id
    version.updated_at = _now()
    if str(who.user.id) not in version.contributors:
        version.contributors = [*version.contributors, str(who.user.id)]
    item.title = p["title"]
    item.topic_id = uuid.UUID(p["topic_id"]) if p.get("topic_id") else None
    if item.kind == "lesson":
        _apply_variant(item, p)
    item.import_hash = r.payload_hash
    item.updated_at = _now()
    if item.state == ItemState.changes_requested.value:
        item.state = ItemState.draft.value
        version.status = VersionStatus.draft.value
    record(
        db,
        actor=who.user.id,
        action="content.imported",
        target_type="content_item",
        target_id=str(item.id),
        details={"batch": str(batch.id), "row": r.row_number, "external_id": r.external_id, "created": False},
    )


def csv_safe(value: object) -> str:
    """Neutralise a cell a spreadsheet would run as a formula (P16.S4.T2: CSV formula injection)."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def report_csv(db: Session, who: Principal, batch_id: uuid.UUID) -> str:
    """The downloadable correction report: one line per row with its action, errors and warnings."""
    batch = _own_batch(db, who, batch_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["row", "external_id", "action", "errors", "warnings", "item_id"])
    for r in rows(db, batch.id):
        w.writerow(
            [
                csv_safe(c)
                for c in (
                    r.row_number,
                    r.external_id,
                    r.action,
                    " | ".join(r.errors),
                    " | ".join(r.warnings),
                    r.item_id,
                )
            ]
        )
    return buf.getvalue()
