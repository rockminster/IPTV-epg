#!/usr/bin/env python3
import os, io, re, gzip, sys, time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
import difflib
import requests

EPG_PW_URL = "https://epg.pw/xmltv/epg_GB.xml.gz"
# Alternative sources - add working ones as they become available
BACKUP_EPG_URLS = [
    # "https://iptv-org.github.io/epg/guides/gb.xml",  # Currently returns 404
]

M3U_URL = os.environ.get("M3U_URL", "").strip()

OUT_DIR = "docs"
OUT_XML_GZ = os.path.join(OUT_DIR, "uk_merged.xml.gz")
OUT_INDEX = os.path.join(OUT_DIR, "index.html")

# Alias map for common UK id mismatches (case-insensitive keys, lowercase output)
ALIAS_MAP = {
  "bbcone.uk": "bbc.one.uk",
  "bbcone": "bbc.one.uk",
  "bbctwo.uk": "bbc.two.uk",
  "bbctwo": "bbc.two.uk",
  "bbc1": "bbc.one.uk",
  "bbc2": "bbc.two.uk",
  "itv1": "itv1.uk",
  "itv 1": "itv1.uk",
  "itv2": "itv2.uk",
  "itv 2": "itv2.uk",
  "itv3": "itv3.uk",
  "itv4": "itv4.uk",
  "channel4": "channel4.uk",
  "ch4": "channel4.uk",
  "more4": "more4.uk",
  "e4": "e4.uk",
  "channel5": "channel5.uk",
  "ch5": "channel5.uk",
  "five": "channel5.uk",
  "skyspremier": "sky.cinema.premiere.uk",
  "skyspremiere": "sky.cinema.premiere.uk",
  "skyscinema.premiere": "sky.cinema.premiere.uk"
}

# ---------------- Normalization helpers ----------------
def normalize_id(tvgid: str) -> str | None:
    if not tvgid:
        return None
    tid = tvgid.strip().lower()
    return ALIAS_MAP.get(tid, tid)

_NAME_PUNCT = re.compile(r"[^a-z0-9+ ]+")
_NAME_SPACE = re.compile(r"\s+")
_NAME_NOISE = re.compile(r"\b(hd|sd|uhd|4k|\+1|plus 1)\b")

def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower()
    n = n.replace("&", " and ")
    n = re.sub(r"\(.*?\)", " ", n)             # drop region/bitrate in parentheses
    n = _NAME_NOISE.sub(" ", n)
    n = _NAME_PUNCT.sub(" ", n)
    n = _NAME_SPACE.sub(" ", n).strip()
    return n

# ---------------- HTTP helpers ----------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "uk-epg-merge/1.1 (+github actions)"})

def check_internet_connectivity():
    """Check basic internet connectivity"""
    test_urls = [
        "https://httpbin.org/ip",
        "https://www.google.com",
        "https://github.com"
    ]
    
    for url in test_urls:
        try:
            r = SESSION.head(url, timeout=5)
            if r.status_code < 400:
                return True
        except:
            continue
    return False

def fetch_epg_source(url, source_name=""):
    """Fetch EPG source with error handling"""
    try:
        print(f"[info] Fetching {source_name or url}...", file=sys.stderr)
        content = fetch(url)
        root = load_xml_root(ungzip_if_needed(content))
        print(f"[info] ✓ Successfully loaded {source_name or url}", file=sys.stderr)
        return root
    except Exception as e:
        print(f"[warn] ✗ Failed to load {source_name or url}: {e}", file=sys.stderr)
        return None
def fetch(url, retries=3, timeout=20):
    last_err = None
    for attempt in range(1, retries+1):
        try:
            r = SESSION.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except Exception as e:
            last_err = e
            time.sleep(1.5 * attempt)
    raise last_err

def ungzip_if_needed(content: bytes) -> bytes:
    if content[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as g:
            return g.read()
    return content

# ---------------- M3U parsing ----------------
M3U_EXTINF = re.compile(r'^#EXTINF.*?,(?P<name>.*)$')
M3U_TVGID = re.compile(r'tvg-id="([^"]+)"')
M3U_TVGNAME = re.compile(r'tvg-name="([^"]+)"')

def parse_m3u_entries(m3u_bytes: bytes):
    """
    Returns list of dicts: { 'id': tvg-id or None, 'name': channel name (best guess) }
    """
    entries = []
    pending = None
    for raw in m3u_bytes.decode("utf-8", "ignore").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            m_id = M3U_TVGID.search(line)
            m_tname = M3U_TVGNAME.search(line)
            m_name = M3U_EXTINF.search(line)
            tvg_id = normalize_id(m_id.group(1)) if m_id else None
            # prefer tvg-name attr; otherwise the display name after comma
            disp_name = m_tname.group(1).strip() if m_tname else (m_name.group("name").strip() if m_name else "")
            entries.append({"id": tvg_id, "name": disp_name})
    return entries

# ---------------- XML helpers ----------------
def load_xml_root(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)

def collect_epg_channels(root: ET.Element):
    """
    Build:
      - id -> set(normalized display names)
      - name_index: normalized name -> set(ids)
    """
    id_to_names = {}
    name_index = {}
    for ch in root.findall("channel"):
        cid_raw = ch.get("id")
        cid = normalize_id(cid_raw)
        if not cid:
            continue
        names = set()
        for dn in ch.findall("display-name"):
            nn = normalize_name(dn.text or "")
            if nn:
                names.add(nn)
        if not names and cid:
            names.add(normalize_name(cid))
        id_to_names[cid] = names
        for nn in names:
            name_index.setdefault(nn, set()).add(cid)
    return id_to_names, name_index

def index_programmes(root: ET.Element):
    d = {}
    for p in root.findall("programme"):
        cid = normalize_id(p.get("channel"))
        if not cid:
            continue
        d.setdefault(cid, []).append(p)
    return d

def prog_key(p: ET.Element):
    start = p.get("start", "")
    stop = p.get("stop", "")
    title = (p.findtext("title") or "").strip().lower()
    return (start, stop, title)

# ---------------- Matching logic ----------------
def resolve_keep_ids(m3u_entries, epg_roots, fuzzy_threshold=0.86):
    """
    Returns a set of EPG channel ids to include, using:
      1) id match (with alias normalization),
      2) exact normalized name match,
      3) fuzzy name match via difflib if best ratio >= threshold.
    """
    # Build channel dictionaries across all EPG roots
    epg_id_to_names = {}
    epg_name_index = {}
    for root in epg_roots:
        id_to_names, name_index = collect_epg_channels(root)
        for cid, names in id_to_names.items():
            epg_id_to_names.setdefault(cid, set()).update(names)
        for nn, ids in name_index.items():
            epg_name_index.setdefault(nn, set()).update(ids)

    keep = set()

    # Precompute a list of (epg_normalized_name, cid) for fuzzy scans
    epg_name_list = []
    for cid, names in epg_id_to_names.items():
        for nn in names:
            epg_name_list.append((nn, cid))

    for ent in m3u_entries:
        mid = ent["id"]
        mid_norm = normalize_id(mid) if mid else None
        mname_norm = normalize_name(ent["name"])

        # 1) id match
        if mid_norm and mid_norm in epg_id_to_names:
            keep.add(mid_norm)
            continue

        # 2) exact name match
        if mname_norm and mname_norm in epg_name_index:
            keep.update(epg_name_index[mname_norm])
            continue

        # 3) fuzzy name match
        if mname_norm:
            best_ratio = 0.0
            best_cid = None
            for nn, cid in epg_name_list:
                ratio = difflib.SequenceMatcher(None, mname_norm, nn).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_cid = cid
            if best_ratio >= fuzzy_threshold and best_cid:
                keep.add(best_cid)

    return keep

# ---------------- Merge ----------------
def merge_guides(roots, keep_ids: set | None):
    merged = ET.Element("tv")
    merged.set("generator-info-name", "uhf-uk-merge")
    merged.set("generator-info-url", "https://github.com/")

    seen_channels = set()
    for r in roots:
        for ch in r.findall("channel"):
            cid = normalize_id(ch.get("id"))
            if not cid:
                continue
            if keep_ids and cid not in keep_ids:
                continue
            if cid in seen_channels:
                continue
            ch.set("id", cid)
            merged.append(ch)
            seen_channels.add(cid)

    programmes = {}
    for r in roots:
        pm = index_programmes(r)
        for cid, plist in pm.items():
            if keep_ids and cid not in keep_ids:
                continue
            programmes.setdefault(cid, []).extend(plist)

    for cid, plist in programmes.items():
        dedup = {}
        for p in plist:
            p.set("channel", cid)
            k = prog_key(p)
            cur = dedup.get(k)
            if cur is None:
                dedup[k] = p
            else:
                cur_desc = (cur.findtext("desc") or "").strip()
                p_desc = (p.findtext("desc") or "").strip()
                if len(p_desc) > len(cur_desc):
                    dedup[k] = p
        for p in sorted(dedup.values(), key=lambda x: (x.get("start",""), x.get("stop",""))):
            merged.append(p)
    return merged

def write_gzip_xml(root: ET.Element, path: str):
    data = ET.tostring(root, encoding="utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wb", compresslevel=6) as f:
        f.write(data)

def main():
    # Check internet connectivity first
    if not check_internet_connectivity():
        print("[error] No internet connectivity detected. This script requires internet access to fetch EPG data.", file=sys.stderr)
        print("[error] Please ensure you have internet access and try again.", file=sys.stderr)
        sys.exit(1)
    
    # Fetch playlist
    m3u_entries = []
    if M3U_URL:
        try:
            m3u_bytes = fetch(M3U_URL)
            m3u_entries = parse_m3u_entries(m3u_bytes)
            print(f"[info] playlist entries: {len(m3u_entries)}", file=sys.stderr)
        except Exception as e:
            print(f"[warn] could not fetch/parse M3U: {e}", file=sys.stderr)

    # Fetch EPG sources with resilient error handling
    epg_roots = []
    
    # Primary source
    epg_pw_root = fetch_epg_source(EPG_PW_URL, "EPG.PW")
    if epg_pw_root is not None:
        epg_roots.append(epg_pw_root)
    
    # Backup sources
    for backup_url in BACKUP_EPG_URLS:
        backup_root = fetch_epg_source(backup_url, f"Backup EPG ({backup_url})")
        if backup_root is not None:
            epg_roots.append(backup_root)
    
    if not epg_roots:
        print("[error] Failed to fetch any EPG sources. Check internet connectivity.", file=sys.stderr)
        sys.exit(1)
    
    print(f"[info] Successfully loaded {len(epg_roots)} EPG source(s)", file=sys.stderr)

    # Resolve which EPG ids to include (id + name fallback)
    keep_ids = resolve_keep_ids(m3u_entries, epg_roots, fuzzy_threshold=0.86)
    if keep_ids:
        print(f"[info] resolved EPG ids to include: {len(keep_ids)}", file=sys.stderr)
    else:
        print("[info] no ids resolved from playlist; including all channels", file=sys.stderr)
        keep_ids = None  # include all

    # Merge & write
    merged = merge_guides(epg_roots, keep_ids)
    write_gzip_xml(merged, OUT_XML_GZ)

    ts = datetime.now(timezone.utc).isoformat()
    with open(OUT_INDEX, "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html>
<html><head><meta charset="utf-8"><title>UK Merged EPG</title></head>
<body>
<h1>UK Merged EPG</h1>
<p>Last build (UTC): {ts}</p>
<p>XMLTV: <a href="uk_merged.xml.gz">uk_merged.xml.gz</a></p>
</body></html>""")

if __name__ == "__main__":
    main()