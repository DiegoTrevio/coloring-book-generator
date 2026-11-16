"""CLI argument parsing and full pipeline orchestration."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import openai
from dotenv import load_dotenv

from .build_receipt import write_receipt
from .cover_layout import layout_covers
from .book_config import BookConfig, load_config
from .review import write_review
from .details_writer import validate, write_upload_details
from .generator import ImageGenerator, SchnellGenerator
from .parser import KDPBook, PageIdea, parse_book
from .pdf_builder import build_pdf
from .postprocess import process_page
from .qa import check_image
from .utils import (
    load_manifest,
    sanitize_folder_name,
    save_manifest,
    setup_logger,
)

log = logging.getLogger("kdp")

# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kdp_book_builder",
        description="Generate everything needed to upload a KDP coloring book to Amazon.",
    )
    p.add_argument("md_file", metavar="MD_FILE", help="Path to the book Markdown file")

    p.add_argument("--config", type=Path, help="Editorial JSON settings: theme, subject, age, style, labels and candidates")
    p.add_argument("--candidates", type=int, help="Generate 1-6 options per drawing (overrides JSON)")
    p.add_argument("--select", default="", help="Select saved options, e.g. 1:2,3:1; use --only-pdf to avoid API calls")
    p.add_argument("--allow-review", action="store_true", help="Include pages flagged for manual review in the PDF")
    p.add_argument("--out",      default=r"D:\KPD",     help="Root output folder (default: D:\\KDP)")
    p.add_argument("--yes",      action="store_true",    help="Skip the Proceed? prompt")
    p.add_argument("--limit",    type=int, default=0,    metavar="N", help="Only generate first N pages")
    p.add_argument("--regen",    default="",             metavar="PAGES", help="Comma-separated page numbers to regenerate, e.g. 7,12,31")
    p.add_argument("--skip-cover",    action="store_true", help="Skip cover generation")
    p.add_argument("--skip-samples",  action="store_true", help="Skip colored-sample image generation")
    p.add_argument("--author",   default="",             help="Override author name in upload_details.txt")
    p.add_argument("--provider", choices=("openai", "replicate"), default="openai", help="Image provider; replicate uses FLUX.1 Schnell")
    p.add_argument("--aspect-ratio", choices=("1:1", "2:3", "3:4", "4:5", "9:16"), default="3:4", help="Schnell aspect ratio (default: 3:4)")
    p.add_argument("--model",    default="gpt-image-2",  help="OpenAI image model (default: gpt-image-2); also supports gpt-image-1, dall-e-3")
    p.add_argument("--quality",  default="",             help="Image quality: low/medium/high (gpt-image-1) or standard/hd (dall-e-3); auto-set if omitted")
    p.add_argument("--size",     default="",             help="Image size; auto-set per model if omitted")
    p.add_argument("--workers",  type=int, default=3,    help="Concurrent generation threads (default: 3)")
    p.add_argument("--threshold",type=int, default=140,  help="B&W threshold 0-255 (default: 140)")
    modes = p.add_mutually_exclusive_group()
    modes.add_argument("--dry-run",   action="store_true",   help="Parse, validate, write upload_details — no API calls")
    modes.add_argument("--only-pdf",  action="store_true",   help="Rebuild PDF and upload_details from existing images")
    modes.add_argument("--only-cover",action="store_true",   help="Generate covers only (skip pages and PDF)")
    return p


# ── API key loading ───────────────────────────────────────────────────────────

def load_api_key(script_dir: Path, provider: str = "openai") -> str:
    load_dotenv(script_dir / ".env")
    variable = "REPLICATE_API_TOKEN" if provider == "replicate" else "OPENAI_API_KEY"
    key = os.environ.get(variable, "").strip()
    if not key:
        sys.exit(
            f"ERROR: {variable} is not set.\n"
            "  Create a .env file next to kdp_book_builder.py with:\n"
            f"    {variable}=your-token\n"
            "  or export the variable in your shell."
        )
    return key


# ── Directory setup ───────────────────────────────────────────────────────────

def setup_dirs(out_root: Path, book_title: str) -> dict[str, Path]:
    book_dir   = out_root / sanitize_folder_name(book_title)
    raw_dir    = book_dir / "pages_raw"
    clean_dir  = book_dir / "pages_clean"
    cover_dir  = book_dir / "cover"
    int_dir    = book_dir / "interior"

    for d in (book_dir, raw_dir, clean_dir, cover_dir, int_dir):
        d.mkdir(parents=True, exist_ok=True)

    return dict(
        book=book_dir, raw=raw_dir, clean=clean_dir,
        cover=cover_dir, interior=int_dir,
    )


# ── Single-page generation + QA loop ─────────────────────────────────────────

_MAX_QA_RETRIES = 3


def _generate_and_qa(
    idea: PageIdea,
    gen: ImageGenerator,
    raw_dir: Path,
    clean_dir: Path,
    manifest: dict,
    manifest_lock: threading.Lock,
    threshold: int,
    force: bool,
    style_prompt: str = "",
    config: BookConfig | None = None,
    generation_id: str = "",
) -> tuple[str, str]:
    """
    Generate one page, run QA, retry up to _MAX_QA_RETRIES on failure.
    Returns (page_key, status).
    """
    key       = f"{idea.number:02d}"
    raw_path  = raw_dir / idea.filename
    clean_path = clean_dir / idea.filename

    config = config or BookConfig(fit_art=False)
    full_prompt = style_prompt + f"\n\nCreate the coloring page for: {idea.idea}"
    fingerprint = hashlib.sha256((full_prompt + generation_id).encode()).hexdigest()
    with manifest_lock:
        page_data = manifest["pages"].get(key, {})
    if not force and page_data.get("status") == "ok" and clean_path.exists():
        if page_data.get("fingerprint") != fingerprint:
            raise ValueError(f"Page {key} has different or legacy settings. Use a new --out folder or --regen {idea.number}.")
        return key, "ok"

    candidates = []
    api_calls = 0
    qa_flags = []
    # Multiple candidates have a predictable number of generation requests.
    # Single-option mode retains the original corrective QA loop.
    count = config.candidates if config.candidates > 1 else 1 + _MAX_QA_RETRIES
    for attempt in range(count):
        candidate_path = raw_dir / f"{idea.number:02d}_candidate_{attempt+1:02d}.png"
        ok = gen.generate(prompt=full_prompt, dest=candidate_path,
                          qa_flags=qa_flags if config.candidates == 1 and attempt else None)
        api_calls += 1
        if not ok:
            continue
        result = check_image(candidate_path)
        qa_flags = result.flags
        candidates.append({"path": candidate_path.name, "qa_flags": result.flags,
                           "dark_pct": float(result.dark_pct),
                           "midtone_pct": float(result.midtone_pct)})
        if config.candidates == 1 and result.ok:
            break
    status = "failed"
    selected = None
    if candidates:
        # Rank technical compliance only, not anatomy or aesthetic quality.
        selected = min(range(len(candidates)), key=lambda i: (
            len(candidates[i]["qa_flags"]), candidates[i]["midtone_pct"]))
        chosen = candidates[selected]
        raw_path.write_bytes((raw_dir / chosen["path"]).read_bytes())
        caption = (config.labels or {}).get(key, (config.labels or {}).get(str(idea.number), "")) if config.captions else ""
        process_page(raw_path, clean_path, threshold, fit_art=config.fit_art, caption=caption)
        qa_flags = chosen['qa_flags']
        status = "needs_review" if qa_flags else "ok"
    with manifest_lock:
        manifest["pages"][key] = {
            "idea": idea.idea, "status": status, "attempts": api_calls,
            "qa_flags": qa_flags, "raw_path": raw_path.name,
            "clean_path": clean_path.name, "candidates": candidates,
            "selected": selected + 1 if selected is not None else None,
            "fingerprint": fingerprint, "visual_reviewed": False,
        }
        manifest["stats"]["api_calls"] = manifest["stats"].get("api_calls", 0) + api_calls

    return key, status


# ── Cover generation ──────────────────────────────────────────────────────────

def _generate_covers(
    gen: ImageGenerator,
    book: KDPBook,
    cover_dir: Path,
    raw_dir: Path,
    n_samples: int,
    manifest: dict,
    skip_samples: bool,
) -> None:
    for name, prompt in (("front", book.front_cover_prompt), ("back", book.back_cover_prompt)):
        dest = cover_dir / f"{name}.png"
        if manifest.get("covers", {}).get(name, {}).get("status") == "ok" and dest.exists():
            log.info("  Cover %s — already OK, skipping", name)
            continue
        log.info("  Generating %s cover ...", name)
        ok = gen.generate(prompt=prompt, dest=dest, max_attempts=3)
        manifest.setdefault("covers", {})[name] = {"status": "ok" if ok else "failed", "path": dest.name}
        if not ok:
            log.error("  Cover %s generation failed after 3 attempts", name)

    if not skip_samples and book.colored_sample_prompt:
        raw_pages = [raw_dir / p["raw_path"] for _, p in sorted(manifest.get("pages", {}).items())
                     if p.get("raw_path") and (raw_dir / p["raw_path"]).exists()][:n_samples]
        for i, src in enumerate(raw_pages, 1):
            dest = cover_dir / f"colored_sample_{i:02d}.png"
            if dest.exists():
                continue
            log.info("  Generating colored sample %d/%d ...", i, n_samples)
            ok = gen.edit(source_path=src, prompt=book.colored_sample_prompt, dest=dest)
            if not ok:
                log.warning("  Colored sample %d skipped (edit endpoint not available)", i)
                break  # if one fails, all will — stop early


# ── QA report writer ──────────────────────────────────────────────────────────

def _write_qa_report(book_dir: Path, manifest: dict) -> None:
    lines = ["KDP Book Builder — QA Report", "=" * 50, ""]
    ok_count = flagged = needs_review = 0
    for key in sorted(manifest["pages"]):
        p = manifest["pages"][key]
        status = p.get("status", "unknown")
        flags  = p.get("qa_flags", [])
        line   = f"  Page {key} [{status:12s}]  {p.get('idea','')[:50]}"
        if flags:
            line += f"  flags: {', '.join(flags)}"
        lines.append(line)
        if status == "ok":
            ok_count += 1
        elif status == "needs_review":
            needs_review += 1
            flagged += 1
        else:
            flagged += 1

    lines.append("")
    lines.append(f"Pages OK:           {ok_count}")
    lines.append(f"Pages flagged/failed:{flagged}  (including {needs_review} needs-manual-review)")
    lines.append(f"API calls made:     {manifest['stats'].get('api_calls', 0)}")
    lines.append("")
    lines.append("COVER: Check cover spelling manually — OCR is not performed.")
    (book_dir / "qa_report.txt").write_text("\n".join(lines), encoding="utf-8")


# ── Main run ──────────────────────────────────────────────────────────────────

def run(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.provider == "replicate":
        if args.size or args.quality:
            parser.error("Schnell uses --aspect-ratio, not --size or --quality")
        if args.model not in ("gpt-image-2", "black-forest-labs/flux-schnell"):
            parser.error("--provider replicate supports only black-forest-labs/flux-schnell")
        args.model = "black-forest-labs/flux-schnell"
        args.skip_samples = True  # Schnell cannot color an existing drawing.
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    try:
        config = load_config(args.config)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    if args.candidates is not None:
        if not 1 <= args.candidates <= 6:
            parser.error("--candidates must be between 1 and 6")
        config.candidates = args.candidates
    if args.select and not args.only_pdf:
        parser.error("Use --select with --only-pdf to select saved images without paid requests")
    md_path = Path(args.md_file).resolve()

    if not md_path.exists():
        sys.exit(f"ERROR: File not found: {md_path}")

    # ── Parse ──────────────────────────────────────────────────────────────
    print(f"\nParsing {md_path.name} ...")
    try:
        book = parse_book(md_path)
    except ValueError as exc:
        sys.exit(str(exc))

    # Page subset
    regen_set: set[int] = set()
    if args.regen:
        try:
            regen_set = {int(x.strip()) for x in args.regen.split(",")}
        except ValueError:
            sys.exit("ERROR: --regen must be comma-separated integers, e.g. 7,12,31")

    ideas = book.page_ideas
    if args.limit > 0:
        ideas = ideas[: args.limit]
    n = len(ideas)
    if len({idea.number for idea in book.page_ideas}) != len(book.page_ideas):
        parser.error("Page numbers must be unique")
    editorial_prompt = config.prompt(book.master_style_prompt) if args.config else book.master_style_prompt

    # ── Setup directories ─────────────────────────────────────────────────
    # ── Model-specific defaults ───────────────────────────────────────────
    _dalle = args.model.startswith("dall-e")
    if not args.size and args.provider == "openai":
        args.size    = "1024x1792" if _dalle else "1024x1536"
    if not args.quality and args.provider == "openai":
        args.quality = "standard"  if _dalle else "medium"

    generation_id = json.dumps([args.provider, args.model, args.size, args.quality,
                                args.aspect_ratio, config.candidates], sort_keys=True)
    out_root = Path(args.out)
    dirs     = setup_dirs(out_root, book.book_title)
    book_dir = dirs["book"]
    log_path = book_dir / "run.log"
    setup_logger(log_path)

    # ── Validate ──────────────────────────────────────────────────────────
    script_dir = Path(__file__).parent.parent
    warnings   = validate(book, len(book.page_ideas), script_dir)
    if warnings:
        print("\n⚠  VALIDATION WARNINGS:")
        for w in warnings:
            print(f"   {w}")

    # ── Print plan ────────────────────────────────────────────────────────
    n_covers    = 0 if (args.skip_cover or args.dry_run or args.only_pdf) else 2
    n_api_pages = n * config.candidates if not (args.dry_run or args.only_pdf or args.only_cover) else 0
    n_samples   = 4 if not (args.skip_samples or args.skip_cover or args.dry_run or args.only_pdf) else 0
    total_calls = n_api_pages + n_covers + n_samples

    print(f"\n{'='*60}")
    print(f"  Book:         {book.book_title}")
    if book.subtitle:
        print(f"  Subtitle:     {book.subtitle}")
    print(f"  Output:       {book_dir}")
    print(f"  Page ideas:   {n}  (total in file: {len(book.page_ideas)})")
    print(f"  Interior PDF: {2 + 2*n + (2 if config.completion_page else 0)} pages (blank backs included)")
    print(f"  Candidates:   {config.candidates} per drawing; technical ranking, visual review required")
    print(f"  API calls:    ~{total_calls}  ({n_api_pages} drawing requests + {n_covers} covers + {n_samples} samples; retries extra)")
    print(f"  Provider:     {args.provider}")
    print(f"  Model:        {args.model}")
    if args.provider == "replicate":
        print(f"  Aspect ratio: {args.aspect_ratio} (4 inference steps)")
        print("  Colored samples disabled: Schnell does not support reference-image editing.")
    else:
        print(f"  Settings:     size={args.size}  quality={args.quality}")
    print(f"  Mode:         {'DRY-RUN' if args.dry_run else 'ONLY-PDF' if args.only_pdf else 'ONLY-COVER' if args.only_cover else 'FULL'}")
    print(f"{'='*60}\n")

    if args.dry_run or args.only_pdf:
        # Write upload_details with placeholder page count
        total_pages = 2 + 2 * n + (2 if config.completion_page else 0)
        interior_pdf = dirs["interior"] / f"{sanitize_folder_name(book.book_title)}_interior.pdf"
        det_path = write_upload_details(
            book, book_dir, interior_pdf, total_pages, warnings, args.author
        )
        print(f"upload_details.txt written → {det_path}")
        if args.dry_run:
            print("\nDRY-RUN complete — no API calls made.")
            return
        # only_pdf falls through to PDF builder below

    if not (args.dry_run or args.only_pdf or args.only_cover):
        if not args.yes:
            ans = input("Proceed? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                sys.exit("Aborted.")

    # ── Load API key & create client ──────────────────────────────────────
    if not args.only_pdf:
        api_key = load_api_key(script_dir, args.provider)
        if args.provider == "replicate":
            import replicate
            gen = SchnellGenerator(replicate.Client(api_token=api_key), args.aspect_ratio)
        else:
            client = openai.OpenAI(api_key=api_key)
            gen = ImageGenerator(client, model=args.model, size=args.size, quality=args.quality)

    manifest      = load_manifest(book_dir / "manifest.json")
    manifest_lock = threading.Lock()
    if args.select:
        try:
            selections = [tuple(map(int, part.split(":"))) for part in args.select.split(",")]
            for number, option in selections:
                page = manifest['pages'][f'{number:02d}']
                if option < 1:
                    raise ValueError('Candidate numbers start at 1')
                selected = page['candidates'][option-1]
                source = dirs['raw'] / selected['path']
                caption = (config.labels or {}).get(str(number), (config.labels or {}).get(f'{number:02d}', '')) if config.captions else ''
                process_page(source, dirs['clean'] / page['clean_path'], args.threshold,
                             fit_art=config.fit_art, caption=caption)
                (dirs['raw'] / page['raw_path']).write_bytes(source.read_bytes())
                page.update(status='ok', selected=option, visual_reviewed=True, qa_flags=[])
        except (ValueError, KeyError, IndexError, OSError) as exc:
            sys.exit(f'ERROR: Invalid saved candidate selection: {exc}')
        save_manifest(book_dir / 'manifest.json', manifest)
        write_review(book_dir, manifest)

    # ── only-cover shortcut ───────────────────────────────────────────────
    if args.only_cover:
        print("\n[F] Generating covers only ...\n")
        _generate_covers(
            gen, book, dirs["cover"], dirs["raw"],
            n_samples=4, manifest=manifest, skip_samples=args.skip_samples,
        )
        save_manifest(book_dir / "manifest.json", manifest)
        if args.config:
            layout_covers(dirs['cover'], book.book_title, book.description)
        print("\nCover generation complete.")
        return

    # ── B. Generate interior pages ────────────────────────────────────────
    if not args.only_pdf:
        print(f"\n[B] Generating {n} interior pages (workers={args.workers}) ...\n")

        futures = {}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for idea in ideas:
                force = idea.number in regen_set
                f = pool.submit(
                    _generate_and_qa,
                    idea, gen,
                    dirs["raw"], dirs["clean"],
                    manifest, manifest_lock,
                    args.threshold, force, editorial_prompt, config, generation_id,
                )
                futures[f] = idea

            for done in as_completed(futures):
                idea = futures[done]
                try:
                    key, status = done.result()
                    icon = "✓" if status == "ok" else ("⚠" if status == "needs_review" else "✗")
                    print(f"  {icon} Page {key}: {status}")
                    # Save each completed page, rather than waiting for the book.
                    with manifest_lock:
                        save_manifest(book_dir / "manifest.json", manifest)
                except Exception as exc:
                    log.error("Unexpected error on page %s: %s", idea.number, exc)
                    manifest['pages'][f'{idea.number:02d}'] = {
                        **manifest['pages'].get(f'{idea.number:02d}', {}),
                        'status': 'failed', 'error': str(exc), 'idea': idea.idea,
                    }

        save_manifest(book_dir / "manifest.json", manifest)

        write_review(book_dir, manifest)
        # Generation failures always stop; flagged images are gated below.
        failed_pages = [
            f"{idea.number:02d}" for idea in ideas
            if manifest["pages"].get(f"{idea.number:02d}", {}).get("status") == "failed"
        ]
        if failed_pages:
            _write_qa_report(book_dir, manifest)
            print(f"\n✗ {len(failed_pages)} page(s) failed to generate: {', '.join(failed_pages)}")
            print("  Fix the error above and re-run — resume mode will skip successful pages.")
            sys.exit(1)

        # ── F. Covers ─────────────────────────────────────────────────────
        if not args.skip_cover:
            print("\n[F] Generating covers ...\n")
            _generate_covers(
                gen, book, dirs["cover"], dirs["raw"],
                n_samples=4, manifest=manifest, skip_samples=args.skip_samples,
            )
            save_manifest(book_dir / "manifest.json", manifest)

    if args.config:
        layout_covers(dirs['cover'], book.book_title, book.description)
    blocked = [f"{idea.number:02d}" for idea in ideas
               if manifest['pages'].get(f"{idea.number:02d}", {}).get('status') != 'ok']
    if blocked and not args.allow_review:
        _write_qa_report(book_dir, manifest)
        write_review(book_dir, manifest)
        sys.exit('ERROR: Pages need review: ' + ', '.join(blocked) +
                 '. Open review.html, then use --only-pdf --select PAGE:OPTION. '
                 'Use --allow-review only for a draft PDF.')
    # Reprocess exact selected files for offline layout/configuration changes.
    for idea in ideas:
        page = manifest['pages'].get(f'{idea.number:02d}', {})
        source = dirs['raw'] / page.get('raw_path', idea.filename)
        caption = (config.labels or {}).get(str(idea.number), (config.labels or {}).get(f'{idea.number:02d}', '')) if config.captions else ''
        if source.is_file():
            process_page(source, dirs['clean'] / idea.filename, args.threshold,
                         fit_art=config.fit_art, caption=caption)

    # ── E. Build PDF ──────────────────────────────────────────────────────
    print("\n[E] Building interior PDF ...\n")
    sanitized_title  = sanitize_folder_name(book.book_title)
    interior_pdf     = dirs["interior"] / f"{sanitized_title}_interior.pdf"
    total_pages = build_pdf(dirs["clean"], interior_pdf, [idea.filename for idea in ideas],
                            language=config.language if args.config else ("es" if book.language.lower() in ("spanish", "español", "es") else "en"),
                            title=book.book_title, completion_page=config.completion_page)
    write_receipt(interior_pdf, md_path, args.config,
                  [dirs["clean"] / idea.filename for idea in ideas])
    print(f"  Interior PDF: {interior_pdf}")
    print(f"  Total pages:  {total_pages}  ({'even ✓' if total_pages % 2 == 0 else 'ODD ✗'})")

    # ── G. Write upload_details.txt ───────────────────────────────────────
    det_path = write_upload_details(
        book, book_dir, interior_pdf, total_pages, warnings, args.author
    )

    # ── QA report ─────────────────────────────────────────────────────────
    _write_qa_report(book_dir, manifest)
    write_review(book_dir, manifest)

    # ── Final summary ──────────────────────────────────────────────────────
    stats      = manifest.get("stats", {})
    ok_count   = sum(1 for p in manifest["pages"].values() if p.get("status") == "ok")
    flagged    = sum(1 for p in manifest["pages"].values() if p.get("status") != "ok")
    api_calls  = stats.get("api_calls", 0)

    print("\n" + "=" * 60)
    print("  DONE")
    print(f"  Pages OK:      {ok_count}")
    print(f"  Pages flagged: {flagged}  (see qa_report.txt)")
    print(f"  API calls:     {api_calls}")
    print(f"  Output folder: {book_dir}")
    print(f"  Details file:  {det_path}")
    print("=" * 60 + "\n")
