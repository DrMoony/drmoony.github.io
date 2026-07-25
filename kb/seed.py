#!/usr/bin/env python3
"""
Seed the knowledge base (kb/data/kb.json) from the existing portfolio index.html.
Parses the main sections into categories + items (bilingual plain text).

Run:  python3 kb/seed.py            (writes kb/data/kb.json; refuses to clobber
                                     an existing one unless --force)
      python3 kb/seed.py --force
"""
import re, os, sys, html, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "index.html")
DATA_DIR = os.path.join(HERE, "data")
OUT = os.path.join(DATA_DIR, "kb.json")

S = open(SRC, encoding="utf-8").read()


# ---------- helpers -------------------------------------------------------
def clean(frag):
    if frag is None:
        return ""
    frag = frag.replace("&middot;", "·").replace("&nbsp;", " ")
    frag = re.sub(r"<[^>]+>", "", frag)
    return re.sub(r"\s+", " ", html.unescape(frag)).strip()


def section(sec_id):
    """Slice a top-level <section id=...> ... </section> (sections don't nest)."""
    m = re.search(r'<section\b[^>]*id="' + re.escape(sec_id) + r'"', S)
    if not m:
        return ""
    end = S.find("</section>", m.end())
    return S[m.start():end]


def lx(frag):
    """First (en, ko) plain-text pair from lx spans in a fragment."""
    en = re.search(r'class="[^"]*lx-en[^"]*">(.*?)</span>', frag, re.S)
    ko = re.search(r'class="[^"]*lx-ko[^"]*">(.*?)</span>', frag, re.S)
    return clean(en.group(1)) if en else "", clean(ko.group(1)) if ko else ""


def grab(frag, cls, tag="div"):
    """Inner html of the first <tag class="...cls..."> in frag (no nested same tag)."""
    m = re.search(r'<' + tag + r'\b[^>]*class="[^"]*\b' + re.escape(cls) +
                  r'\b[^"]*"[^>]*>(.*?)</' + tag + r'>', frag, re.S)
    return m.group(1) if m else None


def para_text(inner):
    """A <p> inner -> 'label: text' if it has a .lab span, else plain."""
    m = re.match(r'\s*<span class="lab">(.*?)</span>(.*)', inner, re.S)
    if m:
        return f"{clean(m.group(1))}: {clean(m.group(2))}"
    return clean(inner)


def paras(frag, lang):
    return [para_text(p) for p in
            re.findall(r'<p class="lx-' + lang + r'">(.*?)</p>', frag, re.S)]


def blocks(frag, start_class, tag=r"\w+"):
    """Split frag into sibling blocks each beginning at start_class."""
    idxs = [m.start() for m in
            re.finditer(r'<' + tag + r'\b[^>]*class="[^"]*\b' + re.escape(start_class) +
                        r'\b[^"]*"', frag)]
    out = []
    for i, st in enumerate(idxs):
        end = idxs[i + 1] if i + 1 < len(idxs) else len(frag)
        out.append(frag[st:end])
    return out


CATS, ITEMS = [], []


def cat(cid, name):
    CATS.append(dict(id=cid, name=name, order=len(CATS)))


def item(cid, title, title_en="", body="", body_en="", tags=None, meta=None):
    ITEMS.append(dict(
        id=f"{cid}-{sum(1 for x in ITEMS if x['category'] == cid) + 1:02d}",
        category=cid, order=sum(1 for x in ITEMS if x["category"] == cid),
        title=title or title_en, title_en=title_en,
        body=body, body_en=body_en,
        tags=tags or [], meta=meta or {}, updated="",
    ))


# ---------- 1. 경력 (career timeline) -------------------------------------
cat("career", "경력 (Career)")
sec = section("career")
for b in blocks(sec, "tl-item"):
    ix = clean(grab(b, "ix"))
    yr = clean(grab(b, "yr"))
    org = clean(grab(b, "org"))
    role_en, role_ko = lx(grab(b, "role") or "")
    h3 = re.search(r"<h3>(.*?)</h3>", b, re.S)
    t_en, t_ko = lx(h3.group(1)) if h3 else ("", "")
    q_en, q_ko = lx(grab(b, "tl-quote") or "")
    tags = [clean(t) for t in re.findall(r'<span class="tag">(.*?)</span>', b)]
    meta = {"period": ix, "year": yr, "org": org,
            "role": role_ko or role_en, "role_en": role_en}
    if q_ko or q_en:
        meta["quote"] = q_ko
        meta["quote_en"] = q_en
    item("career", t_ko, t_en,
         "\n\n".join(paras(b, "ko")), "\n\n".join(paras(b, "en")),
         tags, meta)

# ---------- 2. 주요 사례 (selected work) ----------------------------------
cat("work", "주요 사례 (Selected Work)")
sec = section("work")
work_area = sec[:sec.find('class="wr-coverage"')]
for b in blocks(work_area, "work-row"):
    k = clean(grab(b, "k"))
    t_en, t_ko = lx(grab(b, "wr-title") or "")
    s_en, s_ko = lx(grab(b, "wr-sub") or "")
    big = clean(grab(b, "big"))
    cap_en, cap_ko = lx(grab(b, "cap") or "")
    cid = re.search(r'id="(case-[^"]+)"', b)
    meta = {"context": k, "metric": big}
    if cap_ko or cap_en:
        meta["metric_note"] = cap_ko or cap_en
    if cid:
        meta["anchor"] = "#" + cid.group(1)
    item("work", t_ko, t_en,
         (s_ko + "\n\n" if s_ko else "") + "\n\n".join(paras(b, "ko")),
         (s_en + "\n\n" if s_en else "") + "\n\n".join(paras(b, "en")),
         [], meta)

# ---------- 3. 역량 (competencies) ----------------------------------------
cat("competency", "역량 (Competencies)")
sec = section("model")
for b in blocks(sec, "cw-node", tag="button"):
    num = re.search(r'class="cn-num">(.*?)</span>', b)
    t_en, t_ko = lx(b)
    item("competency", t_ko, t_en, "", "", [],
         {"num": clean(num.group(1)) if num else ""})

# ---------- 4. AX 도구 (tools) --------------------------------------------
cat("tools", "AX 도구 (Tools)")
sec = section("ax")
# group boundary = the second demos label
split_at = sec.find("demos-label-2")
for b in blocks(sec, "tool"):
    pos = sec.find(b[:40])
    group = "company" if (split_at != -1 and pos > split_at) else "personal"
    name = clean(re.search(r"<h4>(.*?)</h4>", b, re.S).group(1)) if re.search(r"<h4>", b) else ""
    r_en, r_ko = lx(grab(b, "role") or "")
    f_en, f_ko = lx(grab(b, "flag", "span") or "")
    d_en = clean(re.search(r'<p class="lx-en">(.*?)</p>', b, re.S).group(1)) if re.search(r'<p class="lx-en">', b) else ""
    d_ko = clean(re.search(r'<p class="lx-ko">(.*?)</p>', b, re.S).group(1)) if re.search(r'<p class="lx-ko">', b) else ""
    link = re.search(r'<a class="live" href="(.*?)"', b)
    meta = {"role": r_ko or r_en, "status": f_ko or f_en, "group": group}
    if link:
        meta["link"] = link.group(1)
    item("tools", name, name, d_ko, d_en, [], meta)

# ---------- 5. 수상 (awards) ----------------------------------------------
cat("awards", "수상 (Awards)")
sec = section("awards")
for b in blocks(sec, "aw"):
    yr = clean(grab(b, "yr"))
    nm = re.search(r'class="nm">(.*?)</div>', b)
    nm = clean(nm.group(1)) if nm else ""
    w_en, w_ko = lx(grab(b, "why") or "")
    by = clean(grab(b, "by"))
    link = re.search(r'data-link="(.*?)"', b)
    if not nm:
        continue
    meta = {"year": yr, "by": by}
    if link:
        meta["anchor"] = link.group(1)
    item("awards", nm, nm, w_ko, w_en, [], meta)

# ---------- 6. 학력·자격 (education) --------------------------------------
cat("education", "학력·자격 (Education)")
sec = section("background")
edu_col = sec[:sec.find('<h3><span class="lx-en">Selected Publications')]
group = ""
for m in re.finditer(r'<h3[^>]*>(.*?)</h3>|<div class="bg-item">(.*?)</div>\s*</div>',
                     edu_col, re.S):
    if m.group(1) is not None:
        ge, gk = lx(m.group(1))
        group = gk or clean(m.group(1))
    else:
        inner = m.group(2)
        h_en, h_ko = lx(inner) if "lx-en" in inner.split("</div>")[0] else ("", "")
        h_raw = grab("<div>" + inner + "</div></div>", "h") or ""
        he, hk = lx(h_raw)
        title = hk or he or clean(h_raw)
        mm = grab("<div>" + inner + "</div></div>", "m") or ""
        me, mk = lx(mm)
        item("education", title, he, mk or clean(mm), me, [], {"group": group})

# ---------- 7. 논문·강연 (publications) -----------------------------------
cat("pub", "논문·강연 (Publications)")
sec = section("background")
pub_area = sec[:sec.find("Invited Talk")] if "Invited Talk" in sec else sec
for b in blocks(pub_area, "pub"):
    t_en, t_ko = lx(b)
    t = t_ko or t_en or clean(grab(b, "t"))
    j = clean(grab(b, "j"))
    item("pub", t, t_en, "", "", [], {"venue": j, "type": "paper"})
# invited talk (bg-item right after the Invited Talk heading)
talk = re.search(r'Invited Talk.*?<div class="bg-item">(.*?)</div>\s*</div>\s*</div>', sec, re.S)
if talk:
    inner = talk.group(1)
    h = clean(grab(inner + "</div>", "h"))
    me, mk = lx(grab(inner + "</div>", "m") or "")
    item("pub", h, h, "", "", [], {"venue": mk or me, "type": "talk"})

# ---------- 8. 철학·노트 (notes) ------------------------------------------
cat("notes", "철학·노트 (Notes)")
sec = section("notes")
for b in blocks(sec, "note"):
    t_en, t_ko = lx(grab(b, "q") or "")
    p_en = clean(re.search(r'<p class="lx-en">(.*?)</p>', b, re.S).group(1)) if re.search(r'<p class="lx-en">', b) else ""
    p_ko = clean(re.search(r'<p class="lx-ko">(.*?)</p>', b, re.S).group(1)) if re.search(r'<p class="lx-ko">', b) else ""
    item("notes", t_ko, t_en, p_ko, p_en)
# AX governing quote + cap (philosophy)
axs = section("ax")
gov_en, gov_ko = lx(grab(axs, "gov", "div") or "")
if gov_ko:
    item("notes", "AX를 보는 관점", "How I see AX", gov_ko, gov_en, [], {"source": "AX section"})

# ---------- 9. 소개 (intro / hero) ----------------------------------------
cat("intro", "소개 (Intro)")
hero = section("hero") or S[S.find('class="hero"'):S.find('id="model"')]
he = re.search(r'<p class="r lx-en">(.*?)</p>', S, re.S)
hk = re.search(r'<p class="r lx-ko">(.*?)</p>', S, re.S)
if hk:
    item("intro", "히어로 소개문", "Hero intro", clean(hk.group(1)),
         clean(he.group(1)) if he else "")
intro_lead = re.search(r'<div class="marquee-in.*?<span class="lx-en">(.*?)</span>.*?<span class="lx-ko">(.*?)</span>', S, re.S)


# ---------- write ---------------------------------------------------------
def main():
    if os.path.exists(OUT) and "--force" not in sys.argv:
        raise SystemExit(f"{OUT} already exists — use --force to overwrite.")
    os.makedirs(DATA_DIR, exist_ok=True)
    state = {"categories": CATS, "items": ITEMS}
    json.dump(state, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"categories={len(CATS)}  items={len(ITEMS)}")
    for c in CATS:
        n = sum(1 for i in ITEMS if i["category"] == c["id"])
        print(f"  {c['id']:12} {c['name']:26} {n}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
