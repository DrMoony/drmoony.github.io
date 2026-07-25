#!/usr/bin/env python3
"""
Extract every visible EN/KO string from index.html into an editable .txt sheet
plus a sidecar JSON, so a human can bulk-edit text and have it re-applied exactly.

Run from anywhere:  python3 text-tools/extract.py
Outputs (in text-tools/):
  portfolio_text.txt   <- edit THIS, hand it back
  portfolio_map.json   <- machine mapping (do not edit)
"""
import re, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "index.html")
OUT_TXT = os.path.join(HERE, "portfolio_text.txt")
OUT_MAP = os.path.join(HERE, "portfolio_map.json")


def extract_elements(s):
    """Ordered list of {tag,lang,aria,inner,start,end} for every <p>/<span>
    carrying an lx-en / lx-ko class. start/end are byte offsets of the inner
    HTML (between the tags). Nested same-name tags are balanced."""
    open_re = re.compile(r'<(p|span)\b[^>]*\bclass="[^"]*\blx-(en|ko)\b[^"]*"[^>]*>')
    els = []
    for m in open_re.finditer(s):
        tag, lang, opentag = m.group(1), m.group(2), m.group(0)
        aria = "aria-hidden" in opentag
        inner_start = m.end()
        depth, pos, inner_end = 1, inner_start, None
        op = re.compile(r"<" + tag + r"\b", re.I)
        cp = re.compile(r"</" + tag + r"\s*>", re.I)
        while depth > 0:
            no, nc = op.search(s, pos), cp.search(s, pos)
            if nc is None:
                raise SystemExit(f"unbalanced <{tag}> near offset {inner_start}")
            if no is not None and no.start() < nc.start():
                depth += 1
                pos = no.end()
            else:
                depth -= 1
                if depth == 0:
                    inner_end = nc.start()
                pos = nc.end()
        els.append(dict(tag=tag, lang=lang, aria=aria,
                        inner=s[inner_start:inner_end],
                        start=inner_start, end=inner_end))
    els.sort(key=lambda e: e["start"])
    return els


def pair_by_stream(els):
    """DOM order is per-language grouped (all EN of a block, then all KO), so
    pair the k-th visible EN with the k-th visible KO. Verified aligned."""
    visible = [e for e in els if not e["aria"]]
    en = [e for e in visible if e["lang"] == "en"]
    ko = [e for e in visible if e["lang"] == "ko"]
    assert len(en) == len(ko), f"EN {len(en)} != KO {len(ko)} — pairing unsafe"
    return list(zip(en, ko))


def main():
    s = open(SRC, encoding="utf-8").read()
    els = extract_elements(s)
    pairs = pair_by_stream(els)

    header = [
        "# 포트폴리오 텍스트 편집 시트",
        "# 규칙: [NNN] 헤더와 'EN\\t' / 'KO\\t' 접두는 그대로 두고, 탭 뒤 텍스트만 수정하세요.",
        '# <em>...</em>, <b class="dot">·</b> 같은 태그와 &amp; 는 그대로 두고 글자만 고치면 됩니다.',
        "# 수정할 항목만 고치고 나머지는 그대로 두세요 (변경된 것만 자동 감지).",
        "",
    ]
    lines, mapping = list(header), []
    for idx, (en, ko) in enumerate(pairs, 1):
        nid = f"{idx:03d}"
        lines += [f"[{nid}]", "EN\t" + en["inner"], "KO\t" + ko["inner"], ""]
        mapping.append(dict(
            id=nid,
            en=dict(start=en["start"], end=en["end"], inner=en["inner"]),
            ko=dict(start=ko["start"], end=ko["end"], inner=ko["inner"]),
        ))

    open(OUT_TXT, "w", encoding="utf-8").write("\n".join(lines))
    json.dump(mapping, open(OUT_MAP, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    aria = sum(1 for e in els if e["aria"])
    print(f"elements={len(els)}  pairs={len(pairs)}  aria-twins(skipped)={aria}")
    print("wrote", OUT_TXT)
    print("wrote", OUT_MAP)


if __name__ == "__main__":
    main()
