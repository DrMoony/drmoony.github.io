#!/usr/bin/env python3
"""
Apply an edited portfolio_text.txt back into index.html — text changes only.

Re-extracts index.html live (deterministic, so ids + offsets match the sheet),
diffs each id against the edited sheet, and splices only the changed inner-HTML
by byte offset (bottom-up, so offsets stay valid). aria-hidden twins (marquee)
with identical original text are updated too.

Usage:
  python3 text-tools/apply.py [edited.txt]      # default: text-tools/portfolio_text.txt
  python3 text-tools/apply.py edited.txt --dry   # preview diff, write nothing
"""
import re, os, sys
from extract import extract_elements, pair_by_stream, SRC, HERE

DEFAULT_TXT = os.path.join(HERE, "portfolio_text.txt")


def parse_sheet(path):
    """Return {id: {'en': str, 'ko': str}} from the edited txt."""
    d, cur = {}, None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]") and line[1:-1].isdigit():
            cur = line[1:-1]
            d[cur] = {}
        elif line.startswith("EN\t"):
            d[cur]["en"] = line[3:]
        elif line.startswith("KO\t"):
            d[cur]["ko"] = line[3:]
    return d


def tag_signature(html):
    """Set of tags in a fragment — used to warn if an edit dropped/added tags."""
    return tuple(sorted(re.findall(r"</?[a-zA-Z][^>]*>", html)))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    txt = args[0] if args else DEFAULT_TXT

    s = open(SRC, encoding="utf-8").read()
    els = extract_elements(s)
    pairs = pair_by_stream(els)
    edited = parse_sheet(txt)

    if len(edited) != len(pairs):
        raise SystemExit(f"sheet has {len(edited)} ids but html has {len(pairs)} "
                         f"pairs — regenerate the sheet (extract.py) and re-edit.")

    # map original inner (lang -> list of aria-twin elements) for marquee sync
    twins = {}
    for e in els:
        if e["aria"]:
            twins.setdefault((e["lang"], e["inner"]), []).append(e)

    splices = []   # (start, end, new_inner, label)
    for idx, (en, ko) in enumerate(pairs, 1):
        nid = f"{idx:03d}"
        for lang, el in (("en", en), ("ko", ko)):
            new = edited[nid][lang]
            if new == el["inner"]:
                continue
            if tag_signature(new) != tag_signature(el["inner"]):
                print(f"  ⚠ [{nid}] {lang.upper()} 태그 구성이 바뀜 — 확인 필요:")
                print(f"      old: {el['inner']}")
                print(f"      new: {new}")
            splices.append((el["start"], el["end"], new, f"{nid}/{lang}"))
            # sync aria-hidden twin(s) carrying the same original text (marquee)
            for tw in twins.get((lang, el["inner"]), []):
                splices.append((tw["start"], tw["end"], new, f"{nid}/{lang}~aria"))

    if not splices:
        print("변경 사항 없음 — index.html 그대로.")
        return

    print(f"변경 {len(splices)}건:")
    for st, en_, new, label in sorted(splices):
        old = s[st:en_]
        print(f"  [{label}]")
        print(f"    - {old}")
        print(f"    + {new}")

    if dry:
        print("\n(--dry: 파일 미수정)")
        return

    for st, en_, new, _ in sorted(splices, key=lambda x: -x[0]):
        s = s[:st] + new + s[en_:]
    open(SRC, "w", encoding="utf-8").write(s)
    print(f"\n✔ index.html 반영 완료 ({len(splices)}건).")


if __name__ == "__main__":
    main()
