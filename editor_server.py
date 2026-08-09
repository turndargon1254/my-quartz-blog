#!/usr/bin/env python3
"""
Quartz 本地内容编辑服务器

提供:
  - GET  /                    -> editor.html 编辑页面
  - GET  /api/tree            -> content 目录树
  - GET  /api/file?path=...   -> 读取某个 .md 文件
  - POST /api/write           -> 新建 / 保存文件
  - POST /api/rename          -> 重命名 / 移动文件或目录
  - POST /api/delete          -> 删除文件或目录

用法:
    python editor_server.py [端口, 默认 8848]
然后浏览器打开 http://127.0.0.1:8848
"""
import json
import os
import re
import shutil
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse, parse_qs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "content")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8848


def safe_content_path(relative_path):
    """把请求中的相对路径映射到 content 目录下，并防止目录穿越攻击。"""
    rel = unquote(relative_path).replace("\\", "/")
    # 去掉路径中的 ./ ../ 片段
    parts = []
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        if re.match(r"^[A-Za-z]:", part):
            continue
        parts.append(part)
    clean = "/".join(parts)
    full = os.path.abspath(os.path.join(CONTENT_DIR, clean))
    content_abs = os.path.abspath(CONTENT_DIR)
    if full != content_abs and not full.startswith(content_abs + os.sep):
        raise ValueError("非法路径")
    return full


def list_tree(full_dir, relative_dir=""):
    """递归生成 content 目录树，只包含目录和 .md 文件。"""
    nodes = []
    try:
        entries = sorted(os.listdir(full_dir))
    except OSError:
        return nodes
    for name in entries:
        full = os.path.join(full_dir, name)
        rel = f"{relative_dir}/{name}" if relative_dir else name
        if os.path.isdir(full):
            nodes.append(
                {
                    "name": name,
                    "path": rel,
                    "type": "folder",
                    "children": list_tree(full, rel),
                }
            )
        elif name.lower().endswith(".md"):
            nodes.append({"name": name, "path": rel, "type": "file"})
    return nodes


class EditorHandler(BaseHTTPRequestHandler):
    server_version = "QuartzEditor/1.0"

    # ---------- helpers ----------
    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=200):
        self._send(status, json.dumps(data, ensure_ascii=False))

    def _ok(self, **kwargs):
        data = {"ok": True}
        data.update(kwargs)
        self._json(data)

    def _err(self, message, status=400):
        self._json({"ok": False, "error": message}, status)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    # ---------- routing ----------
    def do_OPTIONS(self):
        self._send(200, "")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/editor.html"):
            self._serve_editor()
            return
        if parsed.path == "/api/tree":
            self._ok(root="content", tree=list_tree(CONTENT_DIR))
            return
        if parsed.path == "/api/file":
            query = parse_qs(parsed.query)
            rel = (query.get("path", [""])[0]) or ""
            try:
                full = safe_content_path(rel)
            except ValueError as e:
                return self._err(str(e))
            if not os.path.isfile(full):
                return self._err("文件不存在", 404)
            with open(full, "r", encoding="utf-8") as f:
                content = f.read()
            self._ok(path=rel, name=os.path.basename(full), content=content)
            return
        self._err("Not Found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        data = self._read_json()
        route = parsed.path

        if route == "/api/file":
            self._save_file(data)
        elif route == "/api/rename":
            self._rename_node(data)
        elif route == "/api/delete":
            self._delete_node(data)
        else:
            self._err("Not Found", 404)

    # ---------- handlers ----------
    def _save_file(self, data):
        rel = data.get("path") or ""
        content = data.get("content") or ""
        try:
            full = safe_content_path(rel)
        except ValueError as e:
            return self._err(str(e))
        if os.path.isdir(full):
            return self._err("同名目录已存在")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        self._ok(path=rel, name=os.path.basename(full))

    def _rename_node(self, data):
        old_rel = data.get("path") or ""
        new_rel = data.get("newPath") or ""
        try:
            old_full = safe_content_path(old_rel)
            new_full = safe_content_path(new_rel)
        except ValueError as e:
            return self._err(str(e))
        if not os.path.exists(old_full):
            return self._err("源文件或目录不存在", 404)
        if old_full == new_full:
            return self._ok(path=new_rel)
        if os.path.exists(new_full):
            return self._err("目标已存在")
        os.makedirs(os.path.dirname(new_full), exist_ok=True)
        os.rename(old_full, new_full)
        self._ok(path=new_rel)

    def _delete_node(self, data):
        rel = data.get("path") or ""
        try:
            full = safe_content_path(rel)
        except ValueError as e:
            return self._err(str(e))
        if not os.path.exists(full):
            return self._err("文件或目录不存在", 404)
        if os.path.isdir(full):
            shutil.rmtree(full)
        else:
            os.remove(full)
        self._ok(path=rel)

    def _serve_editor(self):
        html = os.path.join(BASE_DIR, "editor.html")
        if not os.path.isfile(html):
            return self._err("editor.html 不存在")
        with open(html, "rb") as f:
            body = f.read()
        self._send(200, body, "text/html; charset=utf-8")

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.address_string(), fmt % args))


def main():
    if not os.path.isdir(CONTENT_DIR):
        os.makedirs(CONTENT_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EditorHandler)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 48)
    print("  Quartz 内容编辑器已启动")
    print(f"  编辑页:   {url}")
    print(f"  内容目录: {CONTENT_DIR}")
    print("  按 Ctrl+C 停止")
    print("=" * 48)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()