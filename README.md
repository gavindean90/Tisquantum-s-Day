# Tisquantum’s Day

An illustrated picture book in thirteen spreads. Each edition opens with a separate title cover, followed by one complete 2:1 spread per page.

| Edition | Reading format |
| --- | --- |
| EPUB 3 | Fixed layout for Apple Books, landscape orientation, one spread per screen. The table of contents links to each scene and the page images include text transcriptions. |
| PDF | Fourteen landscape pages, 887 × 443.5 points, with the full-resolution artwork embedded losslessly. |
| CBZ | Fourteen zero-padded PNG files in reading order, plus ComicInfo metadata. |

## Build locally

Use Python 3.12. From the repository root, run:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python build.py
```

The output files are `dist/tisquantums-day.epub`, `dist/tisquantums-day.pdf` and `dist/tisquantums-day.cbz`. The build fixes ZIP timestamps, omits PDF creation timestamps and uses the dedicated illustrated cover uploaded with the revised spreads. Each story page retains its embedded lettering. EPUB and CBZ store the exact uploaded PNG bytes. The PDF embeds the PNG artwork losslessly.

To run the same EPUB validation locally, unpack the W3C EPUBCheck 5.3.0 distribution and run the following with Java:

```sh
java -jar /path/to/epubcheck-5.3.0/epubcheck.jar dist/tisquantums-day.epub --failonwarnings
```

## Page order and source review

[book.json](book.json) records the reading order, original filenames or pinned revision candidates, source digests, scene labels and text transcriptions. The revised edition uses a dedicated cover and replaces spreads 4, 7, 8 and 9. The four superseded files remain in the repository but are excluded from all editions. Spread 12 looks back on the journey, and spread 13 addresses the reader about Thanksgiving.

The build checks that entries are numbered 1–13 in order, all root PNGs are active or explicitly superseded, active images have a 2:1 aspect ratio, source digests match and no two inputs decode to the same RGB pixels. Three re-encoded replacement uploads are pinned by Git blob digest and matched to the approved artwork using 16 × 8 RGB reference thumbnails. Ambiguous matches fail the build; the selected filename for each spread is printed in CI. For a future editorial revision, review the new spread and update its manifest record and the edition’s modified timestamp.

## Builds and releases

Every push and manual **Actions → Publish ebooks → Run workflow** invocation builds the three editions and runs EPUBCheck before uploading the **tisquantums-day-editions** artifact. Download and unzip the artifact to obtain a single `tisquantums-day-editions/` folder containing all three editions. Open an individual edition from that folder.

To publish a reviewed commit, push a tag pointing to it, for example:

```sh
git tag v1.0.0 <reviewed-commit>
git push origin v1.0.0
```

The tag build attaches all three validated editions as individual downloads on the [GitHub Releases page](https://github.com/gavindean90/Tisquantum-s-Day/releases). Rerunning a tag build refreshes the assets on its existing release.
