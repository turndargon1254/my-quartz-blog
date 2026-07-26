import os
import json
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

try:
    import webview
except ImportError:
    print("错误: 请先在终端运行 pip install pywebview")
    exit(1)

# 设置界面主题风格
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# HTML 模板：引入了业界顶尖的 Vditor 块级/所见即所得 Markdown 编辑器 (与 Notion / WordPress 极其相似)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <link rel="stylesheet" href="https://unpkg.com/vditor@3.9.6/dist/index.css" />
    <script src="https://unpkg.com/vditor@3.9.6/dist/index.min.js"></script>
    <style>
        body, html { margin: 0; padding: 0; height: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        #vditor { height: 100vh !important; border: none !important; }
        .vditor-toolbar { border-bottom: 1px solid #e1e4e8 !important; background-color: #fafbfc !important; }
    </style>
</head>
<body>
    <div id="vditor"></div>
    <script>
        let vditor;
        window.addEventListener('DOMContentLoaded', () => {
            vditor = new Vditor('vditor', {
                height: '100vh',
                mode: 'wysiwyg', // 所见即所得模式 (WordPress 风格)
                toolbar: [
                    'emoji', 'headings', 'bold', 'italic', 'strike', 'link', '|',
                    'list', 'ordered-list', 'check', 'outdent', 'indent', '|',
                    'quote', 'line', 'code', 'inline-code', 'insert-before', 'insert-after', '|',
                    'upload', 'record', 'table', '|',
                    'undo', 'redo', '|',
                    'edit-mode', 'content-theme', 'code-theme', 'outline', 'preview'
                ],
                cache: { enable: false },
                placeholder: '开始像 WordPress 一样输入或粘贴内容吧...',
            });
        });

        // 供 Python 调用的接口
        function setContent(markdown) {
            if (vditor) {
                vditor.setValue(markdown);
            } else {
                setTimeout(() => setContent(markdown), 200);
            }
        }

        function getContent() {
            return vditor ? vditor.getValue() : '';
        }
    </script>
</body>
</html>
"""

class API:
    """ Python 与 JS 通信 bridge """
    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

class QuartzWPEditor(ctk.CTk):
    def __init__(self, content_dir):
        super().__init__()

        self.content_dir = os.path.abspath(content_dir)
        self.current_filepath = None

        self.title("Quartz 博客 - WordPress 风格可视化编辑器")
        self.geometry("1280 x 780")

        # 布局定义
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ------------------ 左侧栏：目录与功能 ------------------
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.label_sidebar = ctk.CTkLabel(self.sidebar_frame, text="📑 文章列表", font=ctk.CTkFont(size=16, weight="bold"))
        self.label_sidebar.pack(pady=10, padx=10, anchor="w")

        # 文件目录树
        self.tree = ttk.Treeview(self.sidebar_frame, show="tree")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # 刷新与发布按钮
        self.btn_refresh = ctk.CTkButton(self.sidebar_frame, text="🔄 刷新文件目录", command=self.load_file_tree)
        self.btn_refresh.pack(fill="x", padx=10, pady=5)

        self.btn_push = ctk.CTkButton(
            self.sidebar_frame, 
            text="🚀 一键更新并推送至 GitHub", 
            fg_color="#28a745", 
            hover_color="#218838",
            command=self.push_to_github
        )
        self.btn_push.pack(fill="x", padx=10, pady=10)

        # ------------------ 右侧栏：文章与富文本编辑 ------------------
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=1)

        # 标题栏
        self.lbl_title = ctk.CTkLabel(self.main_frame, text="文章标题:")
        self.lbl_title.grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.entry_title = ctk.CTkEntry(self.main_frame, placeholder_text="输入文章标题...")
        self.entry_title.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # 标签与草稿
        self.lbl_tags = ctk.CTkLabel(self.main_frame, text="标签分类:")
        self.lbl_tags.grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.entry_tags = ctk.CTkEntry(self.main_frame, placeholder_text="多个标签用逗号隔开")
        self.entry_tags.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.chk_draft_var = ctk.BooleanVar(value=False)
        self.chk_draft = ctk.CTkCheckBox(self.main_frame, text="存为草稿 (不发布)", variable=self.chk_draft_var)
        self.chk_draft.grid(row=1, column=2, padx=10, pady=5)

        # 保存按钮
        self.btn_save = ctk.CTkButton(self.main_frame, text="💾 保存页面", command=self.save_current_file)
        self.btn_save.grid(row=0, column=2, padx=10, pady=5)

        # 网页编辑器容器 (Webview 宿主)
        self.web_container = ctk.CTkFrame(self.main_frame)
        self.web_container.grid(row=3, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")

        # 初始化编辑器引擎
        self.api = API()
        self.web_window = None

        # 初始化加载
        self.load_file_tree()
        self.after(500, self.embed_webview)

    def embed_webview(self):
        """ 将 PyWebView 嵌入到 GUI 编辑框区域 """
        # 在临时文件夹里生成带有所见即所得编辑器的 HTML
        temp_html_path = os.path.join(os.path.dirname(self.content_dir), "editor_tmp.html")
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(HTML_TEMPLATE)

        # 启动嵌入式 Chrome/Edge 内核
        self.web_window = webview.create_window(
            'Editor',
            url=f"file:///{temp_html_path}",
            js_api=self.api,
            frameless=True
        )
        self.api.set_window(self.web_window)

        # 将 webview 绑定在 GUI 上
        webview.start(gui='tkinter', debug=False)

    def load_file_tree(self):
        """ 扫描 content 目录 """
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not os.path.exists(self.content_dir):
            return

        def add_node(parent_node, path):
            for entry in os.scandir(path):
                if entry.is_dir():
                    node = self.tree.insert(parent_node, "end", text=f"📁 {entry.name}", open=True)
                    add_node(node, entry.path)
                elif entry.name.endswith(".md"):
                    self.tree.insert(parent_node, "end", text=f"📄 {entry.name}", values=[entry.path])

        root_node = self.tree.insert("", "end", text="content (根目录)", open=True)
        add_node(root_node, self.content_dir)

    def on_file_select(self, event):
        """ 选择文章时加载所见即所得内容 """
        selected = self.tree.selection()
        if not selected:
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            return

        filepath = values[0]
        self.current_filepath = filepath
        self.read_markdown_file(filepath)

    def read_markdown_file(self, filepath):
        """ 解析 Frontmatter 并将正文注入所见即所得编辑器 """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        title, tags, is_draft, body = "", "", False, content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                header = parts[1]
                body = parts[2].lstrip()
                for line in header.splitlines():
                    if line.startswith("title:"):
                        title = line.replace("title:", "").strip().strip('"').strip("'")
                    elif line.startswith("tags:"):
                        tags = line.replace("tags:", "").strip()
                    elif line.startswith("draft:"):
                        is_draft = "true" in line.lower()

        self.entry_title.delete(0, tk.END)
        self.entry_title.insert(0, title)

        self.entry_tags.delete(0, tk.END)
        self.entry_tags.insert(0, tags)

        self.chk_draft_var.set(is_draft)

        # 转换为 JS 转义字符串并注入富文本编辑器
        if self.web_window:
            escaped_body = json.dumps(body)
            self.web_window.evaluate_js(f"setContent({escaped_body})")

    def save_current_file(self):
        """ 从富文本编辑器获取渲染好的内容并保存 """
        if not self.current_filepath:
            messagebox.showwarning("提示", "请先在左侧选择要修改的文章！")
            return

        title = self.entry_title.get().strip()
        tags = self.entry_tags.get().strip()
        is_draft = self.chk_draft_var.get()

        # 从 JS 编辑器获取 Markdown
        body = self.web_window.evaluate_js("getContent()") if self.web_window else ""

        frontmatter = "---\n"
        if title:
            frontmatter += f'title: "{title}"\n'
        if tags:
            frontmatter += f"tags: [{tags}]\n"
        frontmatter += f"draft: {'true' if is_draft else 'false'}\n"
        frontmatter += "---\n\n"

        full_content = frontmatter + body

        try:
            with open(self.current_filepath, "w", encoding="utf-8") as f:
                f.write(full_content)
            messagebox.showinfo("成功", f"文章已保存！")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def push_to_github(self):
        """ 自动化 Git 提交与推送 """
        quartz_dir = os.path.dirname(self.content_dir)

        try:
            subprocess.run(["git", "add", "."], cwd=quartz_dir, check=True)
            subprocess.run(["git", "commit", "-m", "Auto update via WordPress-style Editor"], cwd=quartz_dir, check=True)
            result = subprocess.run(["git", "push", "origin", "main"], cwd=quartz_dir, capture_output=True, text=True)

            if result.returncode == 0:
                messagebox.showinfo("发布成功 🚀", "已成功推送至 GitHub！\nCloudflare Pages 正在自动构建你的最新博客页面。")
            else:
                messagebox.showerror("推送失败", result.stderr)

        except subprocess.CalledProcessError:
            messagebox.showwarning("提示", "未能提交变更（可能当前没有任何新改动）。")

if __name__ == "__main__":
    CONTENT_DIRECTORY = r"D:\Desktop\quartz\content"
    app = QuartzWPEditor(content_dir=CONTENT_DIRECTORY)
    app.mainloop()