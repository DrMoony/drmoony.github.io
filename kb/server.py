#!/usr/bin/env python3
"""
Local knowledge-base manager — tiny stdlib backend + static app.

Run:   python3 kb/server.py            (http://127.0.0.1:8765)
       python3 kb/server.py --port 9000

Data lives in kb/data/kb.json (pretty-printed JSON, git-friendly).
Mutations are POST /api/<action> with a JSON body; each returns the full state.
Local-only (binds 127.0.0.1). No external dependencies.
"""
import json, os, sys, threading, uuid, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "kb.json")
APP = os.path.join(HERE, "app.html")
LOCK = threading.Lock()


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def load():
    if not os.path.exists(DATA):
        return {"categories": [], "items": []}
    return json.load(open(DATA, encoding="utf-8"))


def save(state):
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    json.dump(state, open(DATA, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def sid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------- mutations (all take state + body, mutate in place) -------------
def m_category_add(s, b):
    s["categories"].append({"id": sid("cat"), "name": b.get("name", "새 카테고리").strip() or "새 카테고리",
                            "order": len(s["categories"])})


def m_category_rename(s, b):
    for c in s["categories"]:
        if c["id"] == b["id"]:
            c["name"] = b.get("name", c["name"]).strip() or c["name"]


def m_category_delete(s, b):
    has = [i for i in s["items"] if i["category"] == b["id"]]
    if has and not b.get("cascade"):
        raise ValueError(f"category has {len(has)} items; pass cascade to delete")
    s["items"] = [i for i in s["items"] if i["category"] != b["id"]]
    s["categories"] = [c for c in s["categories"] if c["id"] != b["id"]]


def m_category_reorder(s, b):
    order = {cid: i for i, cid in enumerate(b["ids"])}
    s["categories"].sort(key=lambda c: order.get(c["id"], 1e9))
    for i, c in enumerate(s["categories"]):
        c["order"] = i


def m_item_add(s, b):
    cat = b["category"]
    n = sum(1 for i in s["items"] if i["category"] == cat)
    s["items"].append({
        "id": sid("itm"), "category": cat, "order": n,
        "title": b.get("title", "").strip(), "title_en": b.get("title_en", "").strip(),
        "body": b.get("body", ""), "body_en": b.get("body_en", ""),
        "tags": b.get("tags", []), "meta": b.get("meta", {}), "updated": now(),
    })


def m_item_update(s, b):
    for i in s["items"]:
        if i["id"] == b["id"]:
            for k in ("title", "title_en", "body", "body_en", "tags", "meta", "category"):
                if k in b:
                    i[k] = b[k]
            i["updated"] = now()


def m_item_delete(s, b):
    s["items"] = [i for i in s["items"] if i["id"] != b["id"]]


def m_item_reorder(s, b):
    order = {iid: i for i, iid in enumerate(b["ids"])}
    for i in s["items"]:
        if i["id"] in order:
            i["order"] = order[i["id"]]


ACTIONS = {
    "category.add": m_category_add, "category.rename": m_category_rename,
    "category.delete": m_category_delete, "category.reorder": m_category_reorder,
    "item.add": m_item_add, "item.update": m_item_update,
    "item.delete": m_item_delete, "item.reorder": m_item_reorder,
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/app.html"):
            try:
                self._send(200, open(APP, "rb").read(), "text/html")
            except FileNotFoundError:
                self._send(404, b"app.html missing", "text/plain")
        elif path == "/api/state":
            with LOCK:
                self._send(200, load())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send(404, {"error": "not found"})
        action = path[len("/api/"):]
        fn = ACTIONS.get(action)
        if not fn:
            return self._send(404, {"error": f"unknown action {action}"})
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        with LOCK:
            state = load()
            try:
                fn(state, body)
            except (KeyError, ValueError) as e:
                return self._send(400, {"error": str(e)})
            save(state)
            self._send(200, state)


def main():
    port = 8765
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"Knowledge Base → http://127.0.0.1:{port}   (Ctrl+C to stop)")
    print(f"data: {DATA}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
