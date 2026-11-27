"""Build the three editions from verified, ordered PNG spreads."""
import base64
import hashlib
import json
import tempfile
from html import escape
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

import img2pdf
from PIL import Image

ROOT = Path(__file__).resolve().parent
SIZE = (1774, 887)
STEM = "tisquantums-day"


def load_book():
    book = json.loads((ROOT / "book.json").read_text(encoding="utf-8"))
    pages = book["spreads"]
    if [p["number"] for p in pages] != list(range(1, 14)):
        raise ValueError("Expected thirteen spreads numbered 1 through 13 in reading order")
    # The three re-encoded uploads have opaque filenames. Match against
    # thumbnails of the approved art, and reject ambiguous matches.
    candidates = {}
    for entry in book["revision_candidates"]:
        path = ROOT / entry["file"]
        data = path.read_bytes()
        git_blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if git_blob != entry["git_blob"]:
            raise ValueError(f"Revision candidate changed: {path.name}")
        with Image.open(path) as im:
            candidates[path.name] = im.convert("RGB").resize(
                (16, 8), Image.Resampling.LANCZOS).tobytes()
    used = set()
    for page in pages:
        if "reference_rgb" not in page:
            continue
        reference = base64.b64decode(page["reference_rgb"], validate=True)
        if len(reference) != 16 * 8 * 3:
            raise ValueError("Invalid reference thumbnail")
        scores = sorted((sum(abs(a-b) for a,b in zip(reference, rgb)) / len(reference), name)
                        for name, rgb in candidates.items())
        score, name = scores[0]
        if score > 5 or scores[1][0] - score < 8 or name in used:
            raise ValueError(f"Ambiguous revision for spread {page['number']}: {scores}")
        used.add(name)
        page["file"] = name
        page["sha256"] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        print(f"Spread {page['number']}: {name} (image distance {score:.2f})")
    if used != set(candidates):
        raise ValueError("Not every revision candidate was selected")
    active = [book["cover"], *pages]
    files = {p["file"] for p in active}
    superseded = set(book["superseded"])
    if (len(files) != 14 or files & superseded
            or files | superseded != {p.name for p in ROOT.glob("*.png")}):
        raise ValueError("Every root PNG must be active or explicitly superseded")
    pixels = set()
    for page in active:
        path = ROOT / page["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != page["sha256"]:
            raise ValueError(f"Source checksum changed: {path.name}")
        with Image.open(path) as im:
            if im.format != "PNG" or im.width != 2 * im.height or im.mode not in ("RGB", "RGBA"):
                raise ValueError(f"Expected a 2:1 RGB or RGBA PNG: {path.name}")
            digest = hashlib.sha256(im.convert("RGB").tobytes()).digest()
        if digest in pixels:
            raise ValueError(f"Duplicate illustration: {path.name}")
        pixels.add(digest)
    return book


def put(archive, name, data):
    # ZipInfo fixes timestamps. Store PNGs directly, with no second deflate pass.
    entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, data, compress_type=ZIP_STORED)


def xhtml(title, head, body):
    return f'''<html xmlns="http://www.w3.org/1999/xhtml"
 xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en" lang="en">
<head><title>{escape(title)}</title>{head}</head><body>{body}</body></html>'''


def write_epub(target, book, pages):
    items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>']
    spine = []
    links = []
    with ZipFile(target, "w") as archive:
        put(archive, "mimetype", "application/epub+zip")
        put(archive, "META-INF/container.xml", '''<container version="1.0"
 xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile
 full-path="EPUB/book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>''')
        width, height = SIZE
        head = f'''<meta name="viewport" content="width={width}, height={height}"/>
<style>html,body{{margin:0;padding:0}} img{{display:block;width:100%;height:auto}}</style>'''
        for i, (source, label, alt) in enumerate(pages):
            page = f"p{i:02}"
            cover = ' properties="cover-image"' if i == 0 else ""
            items.extend([
                f'<item id="{page}" href="{page}.xhtml" media-type="application/xhtml+xml"/>',
                f'<item id="i{i}" href="{page}.png" media-type="image/png"{cover}/>',
            ])
            spine.append(f'<itemref idref="{page}"/>')
            links.append(f'<li><a href="{page}.xhtml">{escape(label)}</a></li>')
            put(archive, f"EPUB/{page}.png", source.read_bytes())
            put(archive, f"EPUB/{page}.xhtml", xhtml(label, head,
                f'<img src="{page}.png" alt="{escape(alt)}"/>'))
        nav = '<nav epub:type="toc"><h1>Contents</h1><ol>' + "".join(links) + "</ol></nav>"
        put(archive, "EPUB/nav.xhtml", xhtml("Contents", "", nav))
        put(archive, "EPUB/book.opf", f'''<package xmlns="http://www.idpf.org/2007/opf"
 version="3.0" unique-identifier="book-id" xml:lang="en">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="book-id">{escape(book["identifier"])}</dc:identifier>
<dc:title>{escape(book["title"])}</dc:title><dc:language>en</dc:language>
<dc:description>{escape(book["description"])}</dc:description>
<meta property="dcterms:modified">{book["modified"]}</meta>
<meta property="rendition:layout">pre-paginated</meta>
<meta property="rendition:orientation">landscape</meta>
<meta property="rendition:spread">none</meta></metadata>
<manifest>{"".join(items)}</manifest><spine page-progression-direction="ltr">
{"".join(spine)}</spine></package>''')


def main():
    book = load_book()
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out) as tmp:
        stage = Path(tmp)
        pages = [(ROOT / p["file"], p["scene"], p["text"]) for p in book["spreads"]]
        cover = book["cover"]
        pages.insert(0, (ROOT / cover["file"], "Cover", cover["text"]))
        write_epub(stage / f"{STEM}.epub", book, pages)
        with ZipFile(stage / f"{STEM}.cbz", "w") as archive:
            for i, (path, _, _) in enumerate(pages):
                put(archive, f"{i:02}.png", path.read_bytes())
            put(archive, "ComicInfo.xml", f'<ComicInfo><Title>{escape(book["title"])}</Title>'
                f'<Summary>{escape(book["description"])}</Summary><LanguageISO>en</LanguageISO>'
                f'<PageCount>{len(pages)}</PageCount><Pages><Page Image="0" Type="FrontCover"/>'
                '</Pages></ComicInfo>')
        with (stage / f"{STEM}.pdf").open("wb") as pdf:
            img2pdf.convert(*(str(path) for path, _, _ in pages), outputstream=pdf,
                engine=img2pdf.Engine.internal, nodate=True, title=book["title"],
                subject=book["description"], layout_fun=img2pdf.get_layout_fun(pagesize=(887, 443.5)))
        for ext in ("epub", "pdf", "cbz"):
            target = out / f"{STEM}.{ext}"
            (stage / target.name).replace(target)
            print(target)


if __name__ == "__main__":
    main()
