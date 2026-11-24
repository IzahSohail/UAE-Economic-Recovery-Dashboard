import re
from pathlib import Path

import pandas as pd
from lxml import etree
from playwright.sync_api import sync_playwright

AGENCY, FLOW, VERSION = "FCSA", "DF_CPI", "3.3.0"
BASE = "https://releaseeuaestat.fcsc.gov.ae/rest"

DEFAULT_START = "2021-01"
STRUCT_URL = f"{BASE}/dataflow/{AGENCY}/{FLOW}/{VERSION}?references=all"


def data_url(start_period: str) -> str:
    return (
        f"{BASE}/data/{AGENCY},{FLOW},{VERSION}/...M.."
        f"?startPeriod={start_period}&dimensionAtObservation=AllDimensions"
    )

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DATA = DATA_DIR / "cpi_monthly.csv"           # data with codes + label columns
OUT_COLS = DATA_DIR / "cpi_metadata_columns.csv"  # full names of the columns

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def local(tag):
    return etree.QName(tag).localname


def kids(el, name):
    return [c for c in el if isinstance(c.tag, str) and local(c.tag) == name]


def names(el, tag="Name"):
    """{lang: text} for Name/Description children."""
    return {c.get(XML_LANG, "en"): (c.text or "").strip() for c in kids(el, tag)}


def ref_id(el, container):
    """Get the id referenced inside e.g. ConceptIdentity or Enumeration."""
    nodes = el.xpath(f".//*[local-name()='{container}']")
    if not nodes:
        return None
    ref = nodes[0].xpath(".//*[local-name()='Ref']")
    if ref:
        return ref[0].get("id")
    text = "".join(nodes[0].itertext()).strip()  # URN style
    m = re.search(r"=[^:]+:([^(\.]+)", text) or re.search(r"\.([^.()]+)$", text)
    return m.group(1) if m else None


# ---------- data parsing ----------
def xml_to_df(xml_text):
    root = etree.fromstring(xml_text.encode("utf-8"))
    rows = []
    for obs in root.iter():
        if not isinstance(obs.tag, str) or local(obs.tag) != "Obs":
            continue
        row = {}
        ch = {local(c.tag): c for c in obs if isinstance(c.tag, str)}
        if "ObsKey" in ch:  # generic format
            for v in ch["ObsKey"]:
                row[v.get("id")] = v.get("value")
            if "ObsValue" in ch:
                row["OBS_VALUE"] = ch["ObsValue"].get("value")
            if "Attributes" in ch:
                for v in ch["Attributes"]:
                    row[v.get("id")] = v.get("value")
        else:  # structure-specific format
            row.update(obs.attrib)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------- structure parsing ----------
def parse_structure(xml_text):
    root = etree.fromstring(xml_text.encode("utf-8"))

    # concept id -> full name
    concepts = {}
    for c in root.iter():
        if isinstance(c.tag, str) and local(c.tag) == "Concept":
            n = names(c)
            concepts[c.get("id")] = n.get("en") or next(iter(n.values()), "")

    # codes (kept in memory to build labels)
    code_rows = []
    for cl in root.iter():
        if not (isinstance(cl.tag, str) and local(cl.tag) == "Codelist"):
            continue
        cl_name = names(cl)
        for code in kids(cl, "Code"):
            n, d = names(code), names(code, "Description")
            code_rows.append({
                "codelist_id": cl.get("id"),
                "codelist_name": cl_name.get("en", ""),
                "code": code.get("id"),
                "name_en": n.get("en", ""),
                "name_ar": n.get("ar", ""),
                "description_en": d.get("en", ""),
            })

    # column (component) table
    kinds = {
        "Dimension": "Dimension",
        "TimeDimension": "TimeDimension",
        "Attribute": "Attribute",
        "PrimaryMeasure": "Measure",
        "Measure": "Measure",
    }
    col_rows = []
    for ds in root.iter():
        if not (isinstance(ds.tag, str) and local(ds.tag) == "DataStructure"):
            continue
        for el in ds.iter():
            if not isinstance(el.tag, str) or local(el.tag) not in kinds:
                continue
            cid = el.get("id") or "OBS_VALUE"
            concept = ref_id(el, "ConceptIdentity") or cid
            col_rows.append({
                "column_id": cid,
                "component_type": kinds[local(el.tag)],
                "position": el.get("position"),
                "full_name": concepts.get(concept, concept),
                "concept_id": concept,
                "codelist_id": ref_id(el, "Enumeration"),
                "assignment_status": el.get("assignmentStatus"),
            })

    # dataflow title
    flow = next(
        (e for e in root.iter() if isinstance(e.tag, str) and local(e.tag) == "Dataflow"), None
    )
    flow_name = names(flow).get("en", "") if flow is not None else ""

    return pd.DataFrame(col_rows), pd.DataFrame(code_rows), flow_name


def add_labels(df, cols_meta, codes_meta):
    out = df.copy()
    for _, c in cols_meta.dropna(subset=["codelist_id"]).iterrows():
        col = c["column_id"]
        if col not in out.columns:
            continue
        sub = codes_meta[codes_meta["codelist_id"] == c["codelist_id"]]
        mapping = dict(zip(sub["code"], sub["name_en"]))
        out.insert(out.columns.get_loc(col) + 1, f"{col}_LABEL", out[col].map(mapping))
    return out


# ---------- fetching ----------
def fetch_xml(page, url, label, retries=3):
    """Load the URL as a normal page visit and return the raw XML body."""
    for attempt in range(1, retries + 1):
        print(f"Fetching {label} (attempt {attempt}/{retries})...")
        resp = page.goto(url, wait_until="domcontentloaded", timeout=120000)
        status = resp.status if resp else None
        ct = resp.headers.get("content-type", "") if resp else ""
        print(f"  HTTP {status} ({ct})")
        if status == 200 and "xml" in ct.lower():
            return resp.body().decode("utf-8-sig")
        page.wait_for_timeout(10000)  # give the browser check time, then retry
    return None


def main(start_period: str = DEFAULT_START):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = data_url(start_period)
    print(f"CPI startPeriod={start_period}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_context().new_page()

        data_xml = fetch_xml(page, url, "data")
        page.wait_for_timeout(3000)  # small pause between requests
        struct_xml = fetch_xml(page, STRUCT_URL, "structure (for labels)")

        browser.close()

    if data_xml is None:
        raise SystemExit("No data returned. Check the printed status above.")

    df = xml_to_df(data_xml)
    if df.empty:
        raise SystemExit("Data response parsed to 0 rows. Check the key and period.")

    if "TIME_PERIOD" in df.columns:
        print(f"Period range: {df['TIME_PERIOD'].min()} -> {df['TIME_PERIOD'].max()}")

    if struct_xml is None:
        print("Could not fetch structure; saving data with codes only.")
        df.to_csv(OUT_DATA, index=False)
        print(f"Saved {len(df)} rows to {OUT_DATA}")
        return

    cols_meta, codes_meta, flow_name = parse_structure(struct_xml)
    cols_meta.to_csv(OUT_COLS, index=False)

    out = add_labels(df, cols_meta, codes_meta)
    out.to_csv(OUT_DATA, index=False)

    print(f"Dataflow: {flow_name}")
    print(f"Saved {len(out)} rows to {OUT_DATA}")
    print(f"Saved {len(cols_meta)} columns to {OUT_COLS}")
    print(out.head())


if __name__ == "__main__":
    main()