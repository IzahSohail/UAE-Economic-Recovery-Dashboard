import io
import re
from pathlib import Path

import pandas as pd
from lxml import etree
from playwright.sync_api import sync_playwright

AGENCY, FLOW, VERSION = "FCSA", "DF_TRADE_SECT_MTH", "5.1.0"
BASE = "https://releaseeuaestat.fcsc.gov.ae/rest"

DEFAULT_START = "2021-01"
STRUCT_URL = f"{BASE}/dataflow/{AGENCY}/{FLOW}/{VERSION}?references=all"


def data_url(start_period: str) -> str:
    return (
        f"{BASE}/data/{AGENCY},{FLOW},{VERSION}/.M......."
        f"?startPeriod={start_period}&dimensionAtObservation=AllDimensions"
    )

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DATA = DATA_DIR / "trade_sect_mth.csv"  # data with codes + label columns
OUT_COLS = DATA_DIR / "metadata_columns.csv"  # full names of the columns

DATA_ACCEPTS = [
    "application/vnd.sdmx.data+csv;version=1.0.0",
    "application/vnd.sdmx.genericdata+xml;version=2.1",
    "application/xml",
]
STRUCT_ACCEPTS = [
    "application/vnd.sdmx.structure+xml;version=2.1",
    "application/xml",
]

JS_FETCH = """
async ([url, accept]) => {
  const r = await fetch(url, {headers: {Accept: accept}});
  return {status: r.status, ct: r.headers.get('content-type') || '', body: await r.text()};
}
"""

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
        if "ObsKey" in ch:
            for v in ch["ObsKey"]:
                row[v.get("id")] = v.get("value")
            if "ObsValue" in ch:
                row["OBS_VALUE"] = ch["ObsValue"].get("value")
            if "Attributes" in ch:
                for v in ch["Attributes"]:
                    row[v.get("id")] = v.get("value")
        else:
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

    # codes table
    code_rows = []
    for cl in root.iter():
        if not (isinstance(cl.tag, str) and local(cl.tag) == "Codelist"):
            continue
        cl_name = names(cl)
        for code in kids(cl, "Code"):
            n, d = names(code), names(code, "Description")
            code_rows.append(
                {
                    "codelist_id": cl.get("id"),
                    "codelist_name": cl_name.get("en", ""),
                    "code": code.get("id"),
                    "name_en": n.get("en", ""),
                    "name_ar": n.get("ar", ""),
                    "description_en": d.get("en", ""),
                    "parent_code": next(
                        (
                            p.get("id")
                            for p in code.xpath(".//*[local-name()='Parent']/*[local-name()='Ref']")
                        ),
                        None,
                    ),
                }
            )

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
            col_rows.append(
                {
                    "column_id": cid,
                    "component_type": kinds[local(el.tag)],
                    "position": el.get("position"),
                    "full_name": concepts.get(concept, concept),
                    "concept_id": concept,
                    "codelist_id": ref_id(el, "Enumeration"),
                    "assignment_status": el.get("assignmentStatus"),
                }
            )

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


def fetch_first_ok(page, url, accepts, want):
    for accept in accepts:
        res = page.evaluate(JS_FETCH, [url, accept])
        print(f"  {accept} -> HTTP {res['status']} ({res['ct']})")
        if res["status"] == 200 and want in res["ct"].lower():
            return res
    return None


def main(start_period: str = DEFAULT_START):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    url = data_url(start_period)
    print(f"Trade startPeriod={start_period}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        page = browser.new_context().new_page()

        print("Opening UAE.Stat (passing the browser check)...")
        page.goto(url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_timeout(15000)

        print("Fetching data...")
        data_res = None
        for accept in DATA_ACCEPTS:
            res = page.evaluate(JS_FETCH, [url, accept])
            print(f"  {accept} -> HTTP {res['status']} ({res['ct']})")
            if res["status"] == 200 and ("csv" in res["ct"].lower() or "xml" in res["ct"].lower()):
                data_res = res
                break

        print("Fetching structure (for labels)...")
        struct_res = fetch_first_ok(page, STRUCT_URL, STRUCT_ACCEPTS, "xml")

        browser.close()

    if data_res is None:
        raise SystemExit("No data returned. Check the printed status codes above.")

    if "csv" in data_res["ct"].lower():
        df = pd.read_csv(io.StringIO(data_res["body"]))
    else:
        df = xml_to_df(data_res["body"])

    if "TIME_PERIOD" in df.columns:
        print(f"Period range: {df['TIME_PERIOD'].min()} -> {df['TIME_PERIOD'].max()}")

    if struct_res is None:
        print("Could not fetch structure; saving data with codes only.")
        df.to_csv(OUT_DATA, index=False)
        return

    cols_meta, codes_meta, flow_name = parse_structure(struct_res["body"])
    cols_meta.to_csv(OUT_COLS, index=False)

    out = add_labels(df, cols_meta, codes_meta)
    out.to_csv(OUT_DATA, index=False)

    print(f"Dataflow: {flow_name}")
    print(f"Saved {len(out)} rows to {OUT_DATA}")
    print(f"Saved {len(cols_meta)} columns to {OUT_COLS}")
    print(out.head())


if __name__ == "__main__":
    main()
