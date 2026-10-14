"""P06.S2.T1 (IMPORT-XLSX-01): the multiple-choice template as an Excel workbook.

* An .xlsx file with the CSV template's columns previews and commits exactly like the CSV file: same validation, same
  drafts. The first worksheet is read; cached cell values are used and formulas are never evaluated.
* The template downloads as .xlsx (columns formatted as text, so IDs keep leading zeros) and as .csv, headings only.
* Hostile or broken workbooks are refused before any row is read: not a zip (old .xls, password-protected), a DOCTYPE
  (entity expansion), a part that inflates past the limit, too many rows, or a column with values but no heading.

Rows are technical fixtures, not academic content.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Any
from xml.sax.saxutils import escape

from fastapi.testclient import TestClient
from sqlalchemy import select

from portal_api.db import get_sessionmaker
from portal_api.modules.content import imports
from portal_api.modules.content.models import ContentItem, ContentVersion
from tests.test_content_import import SCOPE, _author, _preview, _setup
from tests.test_content_workflow import Staff

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _excel_style(rows: list[list[str | int]], *, sheet_extra: str = "", doctype: str = "") -> bytes:
    """A workbook the way Excel saves one: shared strings, numbers as numbers, the sheet found through relationships."""
    strings: list[str] = []
    xml_rows = []
    for ri, row in enumerate(rows, start=1):
        cells = []
        for ci, v in enumerate(row):
            ref = f"{_col(ci)}{ri}"
            if v == "":
                continue
            if isinstance(v, int):
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
            else:
                strings.append(v)
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
        xml_rows.append(f'<row r="{ri}">{"".join(cells)}</row>')
    # Rich-text runs, as Excel writes a cell with mixed formatting, and a phonetic run that is not part of the text.
    sst = "".join(
        f'<si><r><t>{escape(s[:1])}</t></r><r><t xml:space="preserve">{escape(s[1:])}</t></r><rPh><t>x</t></rPh></si>'
        for s in strings
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{REL}/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>',
        )
        z.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets><sheet name="Questions" sheetId="7" r:id="rId9"/>'
            '<sheet name="Notes" sheetId="8" r:id="rId3"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PKG}">'
            f'<Relationship Id="rId3" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
            f'<Relationship Id="rId9" Type="{REL}/worksheet" Target="/xl/worksheets/sheet2.xml"/></Relationships>',
        )
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{NS}">{sst}</sst>')
        z.writestr(
            "xl/worksheets/sheet2.xml",
            f'{doctype}<worksheet xmlns="{NS}">{sheet_extra}<sheetData>{"".join(xml_rows)}</sheetData></worksheet>',
        )
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{NS}"><sheetData/></worksheet>')
    return buf.getvalue()


HEADER = [
    "external_id",
    "chapter",
    "title",
    "stem",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct",
    "explanation",
    "estimated_seconds",
    "source_document_id",
    "pdf_from",
    "pdf_to",
]


def _line(run: str, chapter: str, refs: list[dict[str, Any]], n: int = 0) -> list[str | int]:
    return [
        f"0{n}-FX-{run}",
        chapter,
        "Fixture XLSX",
        f"Fixture XLSX stem {run} {n}",
        "Fixture A",
        "Fixture B",
        "Fixture C",
        "Fixture D",
        "B",
        "Fixture reason",
        90,
        refs[0]["source_document_id"],
        int(refs[0]["pdf_from"]),
        int(refs[0]["pdf_to"]),
    ]


def test_an_excel_workbook_imports_like_the_csv_template(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]
    data = _excel_style([HEADER, _line(run, chapter, refs), [], ["", ""]])  # blank trailing rows are ignored
    r = _preview(client, author, data, fmt="xlsx")
    assert r.status_code == 201, r.text
    batch = r.json()
    assert batch["counts"] == {"create": 1}, batch["rows"]
    done = client.post(f"/v1/studio/imports/{batch['id']}/commit", headers=author.headers)
    assert done.status_code == 200, done.text
    with get_sessionmaker()() as db:
        item = db.scalar(select(ContentItem).where(ContentItem.external_ref == f"00-FX-{run}"))
        assert item is not None and item.kind == "mcq" and item.state == "draft"  # the leading zero survived
        version = db.get(ContentVersion, item.working_version_id)
        assert version is not None
        assert [(b["type"], b["text"]) for b in version.body["stem"]] == [("paragraph", f"Fixture XLSX stem {run} 0")]
        assert version.body["correct_option_id"] == "o2"
        assert version.body["metadata"]["estimated_seconds"] == 90
        assert [o["blocks"][0]["text"] for o in version.body["options"]] == [f"Fixture {x}" for x in "ABCD"]

    # The same rows again change nothing, as with CSV.
    again = _preview(client, author, data, fmt="xlsx").json()
    assert again["counts"] == {"unchanged": 1}, again["rows"]


def test_the_templates_download_with_headings_only(client: TestClient) -> None:
    author = _author(client)
    x = client.get("/v1/studio/imports/templates/mcq.xlsx", headers=author.headers)
    assert x.status_code == 200, x.text
    assert x.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert "mcq-template.xlsx" in x.headers["content-disposition"]
    header, records = imports.xlsx_table(x.content)
    assert header == list(imports.CSV_COLUMNS) and records == []
    with zipfile.ZipFile(io.BytesIO(x.content)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert 'style="1"' in sheet  # every column is formatted as text, so IDs keep their leading zeros
    c = client.get("/v1/studio/imports/templates/mcq.csv", headers=author.headers)
    assert c.status_code == 200 and c.content.startswith(b"\xef\xbb\xbf")  # so Excel opens it as UTF-8
    assert c.content.decode("utf-8-sig").strip() == ",".join(imports.CSV_COLUMNS)
    assert client.get("/v1/studio/imports/templates/mcq.exe", headers=author.headers).status_code == 404
    assert client.get("/v1/studio/imports/templates/mcq.xlsx").status_code == 401
    with get_sessionmaker()() as db:
        learner_like = Staff(client, db, ["support"], SCOPE)
    assert client.get("/v1/studio/imports/templates/mcq.xlsx", headers=learner_like.headers).status_code == 403


def test_unsafe_or_broken_workbooks_are_refused(client: TestClient) -> None:
    author = _author(client)
    chapter, refs = _setup()
    run = uuid.uuid4().hex[:8]

    def reason(data: bytes) -> tuple[int, str | None]:
        r = _preview(client, author, data, fmt="xlsx")
        return r.status_code, r.json().get("code_reason")

    assert reason(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 100) == (422, "XLSX")  # old .xls or password-protected
    assert reason(b"external_id,chapter\n") == (422, "XLSX")
    bomb = '<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>'
    assert reason(_excel_style([HEADER, _line(run, chapter, refs)], doctype=bomb)) == (422, "XLSX")

    # A sheet that inflates far past the limit (it compresses to a few kilobytes) is refused while reading.
    padding = "<sheetPr/>" + " " * (imports.XLSX_MAX_PART + 10)
    inflating = _excel_style([HEADER, _line(run, chapter, refs)], sheet_extra=padding)
    assert len(inflating) < 200_000
    assert reason(inflating)[0] == 413

    too_many = [HEADER] + [_line(run, chapter, refs, n) for n in range(imports.MAX_ROWS + 1)]
    assert reason(_excel_style(too_many))[0] == 413

    headless = [[*HEADER, ""], [*_line(run, chapter, refs), "a value under no heading"]]
    assert reason(_excel_style(headless)) == (422, "CSV_HEADER")
    assert reason(_excel_style([HEADER[:2], [f"FX-{run}", chapter]])) == (422, "CSV_HEADER")  # columns missing
    assert reason(_excel_style([HEADER])) == (422, "EMPTY")
