"""Fetch patent specifications from the KIPRIS Plus Open API.

Usage: python -I tools/kipris.py <application-number> [...] | --all
       python -I tools/kipris.py --pdf <application-number> [...]   (no key: uses data/raw/<appno>.pdf downloaded by hand)
Writes data/raw/<appno>.xml and data/patents/<appno>/biblio.json, fulltext.txt and fig-*.jpg.
biblio.json "holders" is the gazette's (73) 특허권자 (or (71) 출원인 for a published gazette, "holder_kind"); the ending credits use it.
"fulltext_kind" says which gazette fulltext.txt is: "ann" (공고전문, the registered gazette), "pub" (공개전문), or null.
The service key is read from the KIPRIS_API_KEY env var or the project's .env file.
A refused key or a used-up daily quota stops the run (exit 2); rerun once it is fixed and the run resumes.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getBibliographyDetailInfoSearch"
PDF_HOSTS = (".kipris.or.kr",)  # the full-text path the API returns must point back to KIPRIS


def service_key():
    key = os.environ.get("KIPRIS_API_KEY")
    if key:
        return key
    env = os.path.join(ROOT, ".env")
    if os.path.exists(env):
        with open(env, encoding="utf-8-sig") as f:  # -sig: Windows Notepad writes a BOM
            for line in f:
                if line.strip().startswith("KIPRIS_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"\'')
                    if key:
                        return key
    raise SystemExit("KIPRIS_API_KEY not set (put KIPRIS_API_KEY=... in .env or the environment)")


def fetch(appno):
    num = re.sub(r"\D", "", appno)
    url = BASE + "?" + urllib.parse.urlencode({"applicationNumber": num, "ServiceKey": service_key()})
    with urllib.request.urlopen(url, timeout=30) as r:
        raw = r.read()
    os.makedirs(os.path.join(ROOT, "data", "raw"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "raw", num + ".xml"), "wb") as f:
        f.write(raw)
    return num, ET.fromstring(raw)


def text(el, path):
    n = el.find(path)
    return (n.text or "").strip() if n is not None and n.text else ""


class KiprisKeyError(RuntimeError):
    """The key was refused or the daily quota is used up: every later call fails the same way, so the batch stops."""


# KIPRIS answers errors with HTTP 200 and <successYN>N</successYN>; these result codes are about the key or the quota
_KEY_CODES = {"20", "21", "22", "30", "31", "32", "33"}
_KEY_MSG = re.compile(r"KEY|LIMITED_NUMBER|ACCESS_DENIED|EXPIRED|UNREGISTERED_IP|UNSIGNED|서비스\s*키|인증\s*키|트래픽|한도", re.I)


def api_check(root):
    """Raise when the response is an error (KiprisKeyError for key/quota errors); a response with no item is not one."""
    code = text(root, ".//header/resultCode") or text(root, ".//returnReasonCode")  # the latter: data.go.kr gateway format
    if text(root, ".//header/successYN").upper() != "N" and not text(root, ".//returnReasonCode"):
        return
    msg = text(root, ".//header/resultMsg") or text(root, ".//returnAuthMsg") or text(root, ".//errMsg")
    err = f"{code} {msg}".strip() or ET.tostring(root, encoding="unicode")[:300]
    raise (KiprisKeyError if code in _KEY_CODES or _KEY_MSG.search(msg) else RuntimeError)(err)


def parse(root):
    api_check(root)
    item = root.find(".//item")
    if item is None:
        msg = text(root, ".//resultMsg") or text(root, ".//errMsg") or ET.tostring(root, encoding="unicode")[:300]
        raise RuntimeError(msg)
    b = item.find("biblioSummaryInfoArray/biblioSummaryInfo")
    info = {k: text(b, k) for k in (
        "inventionTitle", "inventionTitleEng", "applicationNumber", "applicationDate", "registerNumber",
        "registerDate", "openNumber", "openDate", "publicationNumber", "publicationDate", "registerStatus",
        "claimCount", "originalApplicationKind")} if b is not None else {}
    info["ipc"] = [text(i, "ipcNumber") for i in item.findall("ipcInfoArray/ipcInfo")]
    info["applicants"] = [text(a, "name") for a in item.findall("applicantInfoArray/applicantInfo")]
    info["inventors"] = [text(a, "name") for a in item.findall("inventorInfoArray/inventorInfo")]
    info["abstract"] = text(item, "abstractInfoArray/abstractInfo/astrtCont")
    info["claims"] = [text(c, "claim") for c in item.findall("claimInfoArray/claimInfo")]
    info["images"] = [{k: text(p, k) for k in ("largePath", "path")} for p in item.findall("imagePathInfo")]
    info["rnd"] = [{k: text(r, k) for k in ("rndDepartmentName", "rndProjectName", "rndSpecialInstitutionName", "rndTaskName")}
                   for r in item.findall("rndInfoArray/rndInfo")]
    return info


# ---------------------------------------------------------------- patent holder (특허권자) from the gazette
_ADDR = re.compile(r"(특별시|광역시|특별자치|[가-힣]+도\s|[가-힣]+시\s|[가-힣]+군\s|[가-힣]+구\s|[가-힣\d]+(로|길)\s*\d|번지|\d+-\d+|[가-힣]+(읍|면|동)\s|\b\d{5}\b)")
_CODE = re.compile(r"\(\s*(\d{2})\s*\)")


def holders_from_text(txt):
    """Names under (73) 특허권자 on the gazette front page; (71) 출원인 for a published (unregistered) gazette.
    Returns (names, kind) with kind "73" or "71", or ([], None). Address lines (and their wrapped tails) are dropped."""
    first = txt.split("=====PAGE=====")[0]
    for kind, label in (("73", r"특\s*허\s*권\s*자"), ("71", r"출\s*원\s*인")):
        m = re.search(rf"\(\s*{kind}\s*\)\s*{label}\s*", first)
        if not m:
            continue
        rest = first[m.end():]
        stop = _CODE.search(rest)  # the next INID code, e.g. (72) 발명자
        block = rest[:stop.start()] if stop else rest[:400]
        names = []
        for line in re.split(r"\n+", block):
            line = re.sub(r"\s+", " ", line).strip(" ,;")
            if not line or line[0] in "(（0123456789":  # a wrapped address tail or a postcode
                continue
            cut = _ADDR.search(line + " ")  # an address line, or a name with its address on the same line
            line = (line[:cut.start()] if cut else line).strip(" ,;")
            if line and len(line) <= 60 and line not in names:
                names.append(line)
        if names:
            return names, kind
    return [], None


def gazette_holders(outdir):
    p = os.path.join(outdir, "fulltext.txt")
    if not os.path.exists(p):
        return [], None
    return holders_from_text(open(p, encoding="utf-8").read())


def _kipris_url(url):
    u = urllib.parse.urlparse(url)
    return u.scheme in ("http", "https") and (u.hostname or "").endswith(PDF_HOSTS)


class _KiprisOnly(urllib.request.HTTPRedirectHandler):
    """Follow redirects only while they stay on a KIPRIS host (the first URL is checked by the caller)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _kipris_url(newurl):
            raise RuntimeError("full-text redirect left KIPRIS: " + (urllib.parse.urlparse(newurl).hostname or "?"))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_PDF_OPENER = urllib.request.build_opener(_KiprisOnly)
MAX_PDF = 200 * 2**20


FULLTEXT_OPS = {"ann": "getAnnFullTextInfoSearch", "pub": "getPubFullTextInfoSearch"}  # 공고전문 / 공개전문


def fulltext(num, outdir, registered=False):
    """Download the gazette PDF; extract its text and figure images. A registered patent gets its 공고전문 (the
    (73) 특허권자 and the granted text), falling back to the 공개전문; "kind" in the result says which one it is."""
    err = None
    for kind in ("ann", "pub") if registered else ("pub", "ann"):
        q = urllib.parse.urlencode({"applicationNumber": num, "ServiceKey": service_key()})
        url = BASE.rsplit("/", 1)[0] + "/" + FULLTEXT_OPS[kind] + "?" + q
        with urllib.request.urlopen(url, timeout=30) as r:
            root = ET.fromstring(r.read())
        try:
            api_check(root)
        except KiprisKeyError:
            raise
        except RuntimeError as e:  # an error for this kind only: try the other, and report it if neither has a PDF
            err = e
            continue
        path = text(root, ".//item/path")
        if path:
            break
    else:
        if err:
            raise err
        return None
    u = urllib.parse.urlparse(path)
    if not _kipris_url(path):
        raise RuntimeError("unexpected full-text location: " + (u.hostname or u.scheme or "?"))
    if u.scheme == "http":
        path = urllib.parse.urlunparse(u._replace(scheme="https"))
    pdf = os.path.join(ROOT, "data", "raw", num + ".pdf")
    os.makedirs(os.path.dirname(pdf), exist_ok=True)
    with _PDF_OPENER.open(path, timeout=60) as r:
        data = r.read(MAX_PDF + 1)
    if len(data) > MAX_PDF:
        raise RuntimeError(f"full-text PDF larger than {MAX_PDF // 2**20} MB")
    if b"%PDF" not in data[:1024]:
        raise RuntimeError("full-text download is not a PDF")
    with open(pdf, "wb") as f:
        f.write(data)
    return dict(parse_pdf(pdf, outdir), kind=kind)


def parse_pdf(pdf, outdir):
    """Extract the text and the JPEG figures of a gazette PDF into outdir."""
    import pypdf
    reader = pypdf.PdfReader(pdf)
    with open(os.path.join(outdir, "fulltext.txt"), "w", encoding="utf-8") as f:
        f.write("\n=====PAGE=====\n".join(p.extract_text() or "" for p in reader.pages))
    figs = []
    for i, page in enumerate(reader.pages):
        xo = (page.get("/Resources") or {}).get("/XObject")
        if not xo:
            continue
        for k, v in xo.get_object().items():
            v = v.get_object()
            if v.get("/Filter") == "/DCTDecode" and int(v.get("/Width", 0)) > 200:
                fn = f"fig-p{i + 1}-{re.sub(r'[^A-Za-z0-9_-]', '_', k[1:])}.jpg"
                with open(os.path.join(outdir, fn), "wb") as f:
                    f.write(v._data)
                figs.append(fn)
    return {"pdf": os.path.relpath(pdf, ROOT), "pages": len(reader.pages), "figures": figs}


if __name__ == "__main__":
    import time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # KIPRIS error text can be Korean; a Windows pipe is cp949
    os.makedirs(os.path.join(ROOT, "data", "patents"), exist_ok=True)
    args = sys.argv[1:]
    if args[:1] == ["--pdf"]:
        for a in args[1:]:
            num = re.sub(r"\D", "", a)
            pdf = os.path.join(ROOT, "data", "raw", num + ".pdf")
            if not os.path.exists(pdf):
                print(num, "missing", os.path.relpath(pdf, ROOT))
                continue
            outdir = os.path.join(ROOT, "data", "patents", num)
            os.makedirs(outdir, exist_ok=True)
            ft = parse_pdf(pdf, outdir)
            hs, hk = gazette_holders(outdir)
            with open(os.path.join(outdir, "biblio.json"), "w", encoding="utf-8") as f:
                json.dump({"applicationNumber": num, "claims": [], "source": "pdf", "fulltext": ft, "fulltext_kind": None,
                           "holders": hs, "holder_kind": hk},
                          f, ensure_ascii=False, indent=2)
            print(num, "ok from PDF:", ft["pages"], "pages,", len(ft["figures"]), "figures (claims: read them in fulltext.txt)")
        sys.exit(0)
    if args == ["--all"]:
        master = json.load(open(os.path.join(ROOT, "data", "master.json"), encoding="utf-8"))
        def fetched(a):  # biblio.json with a full text; a failed full-text download is retried on the next run
            p = os.path.join(ROOT, "data", "patents", a, "biblio.json")
            try:
                return bool(json.load(open(p, encoding="utf-8")).get("fulltext"))
            except (OSError, ValueError):
                return False
        args = [m["appno"] for m in master if not fetched(m["appno"])]
        print(len(args), "to fetch", flush=True)
    done = 0
    for i, a in enumerate(args):
        time.sleep(0.3)
        try:
            num, root = fetch(a)
        except Exception as e:  # network hiccup: report and move on, rerun resumes
            print(a, "FETCH ERROR", e, flush=True)
            continue
        try:
            info = parse(root)
            outdir = os.path.join(ROOT, "data", "patents", num)
            os.makedirs(outdir, exist_ok=True)
            try:
                info["fulltext"] = fulltext(num, outdir, registered=bool(info.get("registerNumber")))
            except KiprisKeyError:
                raise
            except Exception as e:
                print(num, "FULLTEXT ERROR", e, flush=True)
                info["fulltext"] = None
        except KiprisKeyError as e:  # every later patent would fail the same way (and spend the quota): stop here
            print(f"{num} KIPRIS key/quota error: {e}\nstopped at {i + 1} of {len(args)} ({done} fetched): check KIPRIS_API_KEY "
                  "(.env or environment) or wait for the daily quota to reset, then rerun (--all resumes)", flush=True)
            sys.exit(2)
        except RuntimeError as e:
            print(num, "ERROR", e)
            continue
        ft = info["fulltext"] or {}
        info["fulltext_kind"] = ft.pop("kind", None)  # kept beside "fulltext", whose shape stays as --pdf writes it
        info["holders"], info["holder_kind"] = gazette_holders(outdir)
        with open(os.path.join(outdir, "biblio.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        done += 1
        if not ft:
            print(num, "ok", len(info["claims"]), "claims, no full text", flush=True)
            continue
        note = ("  (registered, but only the 공개전문 was available)"
                if info.get("registerNumber") and info["fulltext_kind"] == "pub" else "")
        print(num, "ok", len(info["claims"]), "claims,", ft.get("pages"), f"pages ({info['fulltext_kind']}),",
              len(ft.get("figures", [])), "figures" + note, flush=True)
