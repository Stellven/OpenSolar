#!/usr/bin/env python3
"""
wiki-upload-extract.py — Extract text from uploaded documents.

Supports:
  - .pages (Apple Pages) via IWA/snappy protobuf parsing
  - .pdf  via PyMuPDF (fitz)
  - .html/.htm via HTMLParser
  - .md/.txt pass-through

Writes derived text artifacts to <upload_dir>/_extracted/.
Emits explicit extract_failed records when extraction fails.

Usage:
  python3 wiki-upload-extract.py --source <file_or_dir> [--batch <prefix>] [--json]
"""

import argparse
import json
import os
import re
import sys
import zipfile

# ---------------------------------------------------------------------------
# Pages extraction (IWA + snappy)
# ---------------------------------------------------------------------------

def extract_pages_text(pages_path: str) -> dict:
    """Extract text from an Apple .pages file by parsing IWA archives."""
    result = {"status": "pending", "text": "", "error": None, "method": None}

    if not os.path.isfile(pages_path):
        result["status"] = "extract_failed"
        result["error"] = "file_not_found"
        return result

    # Method 1: IWA + snappy decompression (works for modern .pages zip format)
    try:
        import snappy
        text_parts = []
        with zipfile.ZipFile(pages_path) as zf:
            iwa_files = [n for n in zf.namelist() if n.endswith('.iwa')]
            for iwa in iwa_files:
                try:
                    with zf.open(iwa) as f:
                        data = f.read()
                    if len(data) < 5:
                        continue
                    decompressed = snappy.decompress(data[4:])
                    raw = decompressed.decode('utf-8', errors='replace')
                    # Chinese + mixed text
                    chinese = re.findall(
                        r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+'
                        r'(?:[a-zA-Z0-9\s\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]*)*',
                        raw,
                    )
                    # Long ASCII runs
                    ascii_runs = re.findall(r'[a-zA-Z][a-zA-Z0-9\s,.\-:;!?()]{15,}', raw)
                    text_parts.extend(chinese)
                    text_parts.extend(ascii_runs)
                except Exception:
                    pass

        if text_parts:
            result["text"] = '\n'.join(text_parts)
            result["status"] = "success"
            result["method"] = "iwa_snappy"
            return result
    except ImportError:
        pass
    except zipfile.BadZipFile:
        pass

    # Method 2: qlmanage HTML preview fallback (macOS only)
    try:
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            proc = subprocess.run(
                ['qlmanage', '-p', '-o', tmpdir, pages_path],
                capture_output=True, text=True, timeout=30,
            )
            # Find Preview.html in the qlpreview directory
            for d in os.listdir(tmpdir):
                ql_dir = os.path.join(tmpdir, d)
                if os.path.isdir(ql_dir):
                    preview = os.path.join(ql_dir, 'Preview.html')
                    if os.path.isfile(preview):
                        with open(preview) as f:
                            html = f.read()
                        from html.parser import HTMLParser
                        class _TE(HTMLParser):
                            def __init__(self):
                                super().__init__()
                                self.parts = []
                                self._skip = False
                            def handle_starttag(self, tag, attrs):
                                if tag in ('script', 'style'):
                                    self._skip = True
                            def handle_endtag(self, tag):
                                if tag in ('script', 'style'):
                                    self._skip = False
                            def handle_data(self, data):
                                if not self._skip:
                                    t = data.strip()
                                    if t:
                                        self.parts.append(t)
                        te = _TE()
                        te.feed(html)
                        if te.parts:
                            result["text"] = '\n'.join(te.parts)
                            result["status"] = "success"
                            result["method"] = "qlmanage_html"
                            return result
    except Exception:
        pass

    result["status"] = "extract_failed"
    result["error"] = "all_methods_exhausted"
    return result


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: str) -> dict:
    result = {"status": "pending", "text": "", "error": None, "method": None}
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = '\n'.join(pages)
        if text.strip():
            result["text"] = text
            result["status"] = "success"
            result["method"] = "pymupdf"
        else:
            result["status"] = "extract_failed"
            result["error"] = "empty_text"
    except ImportError:
        result["status"] = "extract_failed"
        result["error"] = "pymupdf_not_installed"
    except Exception as e:
        result["status"] = "extract_failed"
        result["error"] = str(e)
    return result


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

def extract_html_text(html_path: str) -> dict:
    from html.parser import HTMLParser
    result = {"status": "pending", "text": "", "error": None, "method": None}
    try:
        with open(html_path, encoding='utf-8', errors='replace') as f:
            html = f.read()
        class _TE(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts = []
                self._skip = False
            def handle_starttag(self, tag, attrs):
                if tag in ('script', 'style'):
                    self._skip = True
            def handle_endtag(self, tag):
                if tag in ('script', 'style'):
                    self._skip = False
            def handle_data(self, data):
                if not self._skip:
                    t = data.strip()
                    if t:
                        self.parts.append(t)
        te = _TE()
        te.feed(html)
        text = '\n'.join(te.parts)
        if text.strip():
            result["text"] = text
            result["status"] = "success"
            result["method"] = "html_parser"
        else:
            result["status"] = "extract_failed"
            result["error"] = "empty_text"
    except Exception as e:
        result["status"] = "extract_failed"
        result["error"] = str(e)
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

EXTRACTORS = {
    '.pages': extract_pages_text,
    '.pdf': extract_pdf_text,
    '.html': extract_html_text,
    '.htm': extract_html_text,
}


def extract_file(source_path: str, output_dir: str = None) -> dict:
    """Extract text from a single file. Returns result dict with artifact path."""
    _, ext = os.path.splitext(source_path)
    ext = ext.lower()

    # Pass-through for already-text formats
    if ext in ('.md', '.txt', '.markdown'):
        with open(source_path, encoding='utf-8', errors='replace') as f:
            text = f.read()
        return {
            "source": os.path.basename(source_path),
            "status": "success",
            "method": "passthrough",
            "error": None,
            "text_length": len(text),
            "text_preview": text[:500],
            "artifact": source_path,
        }

    extractor = EXTRACTORS.get(ext)
    if not extractor:
        return {
            "source": os.path.basename(source_path),
            "status": "extract_failed",
            "method": None,
            "error": f"unsupported_extension:{ext}",
            "text_length": 0,
            "text_preview": None,
            "artifact": None,
        }

    res = extractor(source_path)
    res["source"] = os.path.basename(source_path)

    # Write derived artifact
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(source_path), '_extracted')
    os.makedirs(output_dir, exist_ok=True)

    basename = os.path.basename(source_path)
    name_without_ext = os.path.splitext(basename)[0]
    artifact_path = os.path.join(output_dir, f"{name_without_ext}.extracted.txt")

    with open(artifact_path, 'w', encoding='utf-8') as f:
        if res["status"] == "success":
            f.write(res["text"])
        else:
            f.write(f"[extract_failed: {res['error']}]")

    res["artifact"] = artifact_path
    res["text_length"] = len(res.get("text", ""))
    res["text_preview"] = res.get("text", "")[:500]
    # Don't keep full text in the summary
    res.pop("text", None)

    return res


def extract_batch(upload_dir: str, batch_prefix: str = None) -> dict:
    """Extract all files matching batch_prefix in upload_dir."""
    files = sorted(os.listdir(upload_dir))
    if batch_prefix:
        files = [f for f in files if f.startswith(batch_prefix) and not f.startswith('.')]

    results = []
    for f in files:
        path = os.path.join(upload_dir, f)
        if not os.path.isfile(path):
            continue
        res = extract_file(path)
        results.append(res)

    summary = {
        "batch": batch_prefix or "all",
        "upload_dir": upload_dir,
        "total_files": len(results),
        "extracted": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "extract_failed"),
        "files": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description='Extract text from uploaded documents')
    parser.add_argument('--source', help='Single file or directory to extract')
    parser.add_argument('--batch', help='Batch prefix filter (e.g., 20260508T122047Z)')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    parser.add_argument('--output-dir', help='Override output directory for derived artifacts')
    args = parser.parse_args()

    if not args.source:
        print("Error: --source required", file=sys.stderr)
        sys.exit(1)

    if os.path.isdir(args.source):
        summary = extract_batch(args.source, args.batch)
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(f"Batch: {summary['batch']}")
            print(f"Total: {summary['total_files']}, Extracted: {summary['extracted']}, Failed: {summary['failed']}")
            for f in summary['files']:
                icon = '✓' if f['status'] == 'success' else '✗'
                print(f"  {icon} {f['source']}: {f['status']} ({f.get('text_length', 0)} chars)")
    else:
        res = extract_file(args.source, args.output_dir)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{res['source']}: {res['status']} ({res.get('text_length', 0)} chars)")


if __name__ == '__main__':
    main()
