from __future__ import annotations

import datetime as _dt
import pathlib
import textwrap
import unicodedata


OUTPUT_PATH = pathlib.Path("PP_BOT/data/outputs/cds_ccal_transaction_activity_workflow_report.pdf")


def ascii_text(value: str) -> str:
    value = str(value).replace("•", "-").replace("–", "-").replace("—", "-")
    value = unicodedata.normalize("NFKD", value)
    return value.encode("ascii", "ignore").decode("ascii")


def wrap(text: str, width: int = 92) -> list[str]:
    normalized = ascii_text(" ".join(str(text).split()))
    if not normalized:
        return [""]
    return textwrap.wrap(normalized, width=width, break_long_words=False, break_on_hyphens=False) or [""]


def esc_pdf(text: str) -> str:
    return ascii_text(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_report_lines() -> list[str]:
    sections: list[tuple[str, list[str], list[str]]] = [
        (
            "Executive summary",
            [
                "CDS and CCAL form the transaction, activity, position, and balance processing backbone for the platform.",
                "The flow is centered on Oracle landing, staging, and target layers, with Oracle Data Integrator (ODI) jobs, GoldenGate replication, reference lookups, and exception routing.",
                "Transactions drive activity and cash flow classification, then update positions, balances, tax lots, and cost basis artifacts across CCAL schemas and support tables.",
            ],
            [
                "Primary focus areas: transaction lifecycle, activity derivation, position rollup, and balance aggregation.",
                "Key control themes: auditability, exception handling, reference-data validation, and reconciliations.",
                "Primary technical stack: Oracle schemas, ODI pipelines, GoldenGate streams, and downstream exception tables.",
            ],
        ),
        (
            "CDS / CCAL landscape",
            [
                "CDS is the processing environment that ingests source transactions and supporting reference data.",
                "CCAL is the business/domain layer that manages positions, transactions, cost basis, and performance for accounts and portfolios.",
                "The deck and extracted artifacts show CDS as the staging and processing wrapper around CCAL target structures.",
            ],
            [
                "CCAL manages transactions, positions, balances, tax lots, accrued income, and performance data.",
                "CDS provides the source-to-target plumbing and exception handling for the workflows.",
                "Reference ownership is split from transaction facts to preserve standardization and reuse.",
            ],
        ),
        (
            "Source systems and intake",
            [
                "The transaction flow spans multiple upstream source families: retail/PCG, shadow, RJ Trust, RJ Bank, RJIG, institutional impact, firm/in-house, direct mutual funds, and file or in-memory feeds.",
                "Slides and Visio extracts show sources feeding Oracle landing tables, then staging, and finally target tables.",
                "Some sources are real-time, while others are end-of-day or batch sourced.",
            ],
            [
                "Sources visible in the extracted diagrams include HPNS, Standard Trade Server, RJ Trust, RJ Bank, Shadow, FIS, and file-based sources.",
                "Landing layers are frequently Oracle-based, while some feeds arrive via MQ, files, or in-memory sources.",
                "Source-specific routing feeds later classification and aggregation logic.",
            ],
        ),
        (
            "Transaction lifecycle and activity derivation",
            [
                "Transactions are classified into business activities and subtypes such as trades, transfers, fees, corporate actions, dividends, ACAT, cash deposits, withdrawals, checks, sweeps, and more.",
                "The CCAL transaction slide defines activity as the broader categorization of transactions for client-facing and advisor-facing applications.",
                "The job flow derives new or updated position information from transaction activity and preserves traceability back to the source event.",
            ],
            [
                "Nearly 150 transaction types and roughly 1500 subtypes are referenced in the CCAL transaction material.",
                "Real-time transaction sourcing is used for retail and shadow feeds.",
                "EOD sourcing is used for other sources, with intraday position updates and cash flow derivation where required.",
            ],
        ),
        (
            "Position and balance processing",
            [
                "Position processing includes financial market instruments, cash, annuities, tangible goods, and other position types.",
                "Balance processing rolls up end-of-day position data into target balance structures such as CCAL_SUB_BAL_TGT.",
                "The balance SQL shows validation against CCAL_OWNER.POS and updates to CDS_STG_OWNER.APPLICATION_PROPERTY for the CCAL balance processing date.",
            ],
            [
                "Position details include box location, accounting type, cash type, cash balance, tax lots, and accrued income.",
                "Balance-related control properties include CCAL_BAL_PBD_DT.",
                "The balance workflow appears to use end-of-day position dates and staging checks for duplicates and exceptions.",
            ],
        ),
        (
            "Oracle schemas and core tables",
            [
                "The extracted artifacts reference several core Oracle schemas: CCAL_OWNER, CCAL_REPL_OWNER, CDS_STG_OWNER, CDS_UTIL_OWNER, REFERENCE_OWNER, and various fill or source-specific owners.",
                "Core target tables and structures include POS, TXN, APA, FIP, EOD_POS, AST_LBY_POS, TXN_STG, APA_STG, FIP_STG, CCAL_SUB_BAL_TGT, EXCP_POOL, and EXCP_DTL.",
                "Replication and integration names such as ACTCCALQ_GG and STSCCALQ_GG appear in the Visio flows.",
            ],
            [
                "CCAL_OWNER is the core target area for transaction and position entities.",
                "CCAL_REPL_OWNER holds replicated or GoldenGate-related structures.",
                "CDS_UTIL_OWNER hosts exception pools and exception detail tables.",
                "REFERENCE_OWNER stores account and product reference data used by downstream jobs.",
            ],
        ),
        (
            "ODI processes, markers, and job flow",
            [
                "The Visio extraction shows multiple ODI-driven processes moving data from source systems to landing, landing to staging, and staging to target.",
                "Markers and process names include REOCDS2EOD, FRNCDSBEOD, DIVCDS1BEOD, DIVCDS2BEOD, STRCCDSEOD, ACATCDSEOD, S13CCALEOD, DIVACDSEOD, and TRANCOMPLETE.",
                "Target load jobs include CCAL_PKG_LOAD_TX_STG_MT and other real-time and batch variants.",
            ],
            [
                "CDS staging jobs include business exception handling and reference lookup steps.",
                "Some flows explicitly note no data transformations on target load jobs, while staging flows perform transformations and validations.",
                "GoldenGate replication streams are visible across several CCAL sourcing patterns.",
            ],
        ),
        (
            "Business controls and exception handling",
            [
                "Business exceptions are routed through CDS_UTIL_OWNER exception tables and control tables.",
                "The diagrams show business/missing reference exception handling and operational review paths through an Ops Analyst tool.",
                "The architecture emphasizes traceability across transactions, positions, and balances so downstream reconciliation is possible.",
            ],
            [
                "Reference lookups for account and product are mandatory in several flows.",
                "Exception pools and exception detail tables capture load issues and business-rule failures.",
                "The processing model supports auditability and downstream investigation of failed or incomplete records.",
            ],
        ),
        (
            "Key components",
            [
                "ESActivity supports transaction/activity extraction.",
                "ESAsset, ESLeanAsset, ESLeanCostBasis, and ESPortfolioBalances support position and balance extracts.",
                "The deck material also highlights EOD extracts for positions, position detail, and transactions.",
            ],
            [
                "ODI and GoldenGate are the primary orchestration layers visible in the extracted diagrams.",
                "Landing, staging, target, exception, and reference layers are all part of the operating model.",
                "The workflow is designed to scale across multiple source families and business domains.",
            ],
        ),
        (
            "Risks, assumptions, and access notes",
            [
                "The online SharePoint source was not accessible with the available token, so this report relies on local materials and extracted artifacts.",
                "The wiki source was accessible and used for general context, but the report content here is driven primarily by local decks, diagrams, and SQL artifacts.",
                "Some Visio and image extracts note that OCR was not run in this pass, so a few details are inferred from slide and diagram text.",
            ],
            [
                "Assumption: local presentation decks and extracted SQL/diagram summaries are representative of the current CDS/CCAL design.",
                "Assumption: ODI and GoldenGate naming in the artifacts reflects the operating production patterns.",
                "Assumption: the balance and transaction flows shown are the most relevant current technical themes for the deck.",
            ],
        ),
        (
            "Closing summary",
            [
                "CDS is the integration and control layer; CCAL is the business processing layer for transactions, activities, positions, and balances.",
                "The dominant pattern is source -> landing -> staging -> target, with reference enrichment, exception handling, and end-of-day or real-time processing as required.",
                "The key to the platform is traceable processing across schemas, jobs, and control tables so every transaction can be reconciled into position and balance outputs.",
            ],
            [
                "Use the report as the basis for a presentation-ready technical narrative.",
                "The same source material can be expanded into a PowerPoint deck with speaker notes if needed.",
            ],
        ),
    ]

    lines: list[str] = []
    lines.append("CDS / CCAL Transaction and Activity Workflow Report")
    lines.append("Generated from local CDS workspace materials, extracted diagrams, deck text, and SQL artifacts.")
    lines.append(f"Generated on: {ascii_text(_dt.datetime.now().isoformat(sep=' ', timespec='seconds'))}")
    lines.append("")

    for title, paragraphs, bullets in sections:
        lines.append(title.upper())
        for paragraph in paragraphs:
            lines.extend(wrap(paragraph))
            lines.append("")
        for bullet in bullets:
            lines.extend(wrap(f"- {bullet}"))
        lines.append("")

    lines.append("SOURCE INPUTS USED")
    lines.extend(wrap("Local brief: PP_BOT/cds_workspace/cds_workflow_brief.txt"))
    lines.extend(wrap("Extracted artifacts: diagram_extract_summary.json, CCAL lunch-and-learn slides, CCAL transaction flow diagrams, CCAL balance SQL"))
    lines.extend(wrap("Key schemas and components: CCAL_OWNER, CCAL_REPL_OWNER, CDS_STG_OWNER, CDS_UTIL_OWNER, REFERENCE_OWNER, ODI, GoldenGate, exception tables"))
    return lines


def paginate(lines: list[str], lines_per_page: int = 42) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if len(current) >= lines_per_page:
            pages.append(current)
            current = []
        current.append(line)
    if current:
        pages.append(current)
    return pages


def content_stream_for_page(lines: list[str], *, title_page: bool = False) -> bytes:
    parts: list[str] = []
    parts.append("BT")
    if title_page:
        parts.append("/F1 18 Tf")
        parts.append("18 TL")
        parts.append("50 760 Td")
    else:
        parts.append("/F1 11 Tf")
        parts.append("14 TL")
        parts.append("50 780 Td")

    first = True
    for raw_line in lines:
        line = esc_pdf(raw_line)
        if not first:
            parts.append("T*")
        first = False
        if not line:
            parts.append("() Tj")
        else:
            parts.append(f"({line}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def build_pdf(output_path: pathlib.Path, pages_text: list[list[str]]) -> None:
    objects: list[bytes] = []

    # Placeholder objects; offsets are calculated after all objects are assembled.
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_objects: list[tuple[bytes, bytes]] = []
    content_object_ids: list[int] = []

    obj_id = 4
    for idx, page_lines in enumerate(pages_text):
        stream = content_stream_for_page(page_lines, title_page=(idx == 0))
        content_obj = f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        content_object_ids.append(obj_id + 1)
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {obj_id + 1} 0 R >>"
        ).encode("latin-1")
        page_objects.append((page_obj, content_obj))
        obj_id += 2

    kids = " ".join(f"{4 + i * 2} 0 R" for i in range(len(pages_text)))
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>".encode("latin-1")

    full_objects: list[bytes] = []
    full_objects.append(b"1 0 obj\n" + objects[0] + b"\nendobj\n")
    full_objects.append(b"2 0 obj\n" + objects[1] + b"\nendobj\n")
    full_objects.append(b"3 0 obj\n" + objects[2] + b"\nendobj\n")

    next_obj_num = 4
    for page_obj, content_obj in page_objects:
        full_objects.append(f"{next_obj_num} 0 obj\n".encode("latin-1") + page_obj + b"\nendobj\n")
        full_objects.append(f"{next_obj_num + 1} 0 obj\n".encode("latin-1") + content_obj + b"\nendobj\n")
        next_obj_num += 2

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    body = bytearray()
    body.extend(header)

    obj_offsets: list[int] = []
    for obj in full_objects:
        obj_offsets.append(len(body))
        body.extend(obj)

    xref_start = len(body)
    xref = [b"xref\n", f"0 {len(full_objects) + 1}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    for offset in obj_offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(full_objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode("latin-1")

    body.extend(b"".join(xref))
    body.extend(trailer)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(body))


def main() -> None:
    lines = build_report_lines()
    pages = paginate(lines, lines_per_page=36)
    build_pdf(OUTPUT_PATH, pages)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
