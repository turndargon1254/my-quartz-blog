import os
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk as standard_ttk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from git import Repo, GitCommandError

class QuartzEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quartz Markdown Manager & Publisher")
        self.root.geometry("1100x800")

        # 状态变量
        self.quartz_path = tk.StringVar(value=r"D:\Desktop\quartz")
        self.current_file_path = None

        self._setup_ui()
        # 启动时如果默认路径存在，自动加载文件树
        if os.path.exists(self.quartz_path.get()):
            self.load_markdown_files()

    def _setup_ui(self):
        # 顶栏: 目录选择器
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=X)

        ttk.Label(top_frame, text="Quartz 根目录:").pack(side=LEFT, padx=(0, 5))
        path_entry = ttk.Entry(top_frame, textvariable=self.quartz_path, width=60)
        path_entry.pack(side=LEFT, padx=5, fill=X, expand=True)

        ttk.Button(top_frame, text="浏览...", command=self.browse_folder, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
        ttk.Button(top_frame, text="加载文章", command=self.load_markdown_files, bootstyle=PRIMARY).pack(side=LEFT, padx=5)

        # 主界面分割 (左侧文件树，右侧编辑器)
        paned = standard_ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # 1. 左侧文件树 Frame
        left_frame = ttk.Labelframe(paned, text="文章列表 (content 目录)", padding=5)
        paned.add(left_frame, weight=1)

        self.tree = ttk.Treeview(left_frame, show="tree", selectmode="browse")
        self.tree.pack(fill=BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_file_selected)

        # 2. 右侧编辑区 Frame
        right_frame = ttk.Labelframe(paned, text="编辑区域", padding=5)
        paned.add(right_frame, weight=3)

        # 编辑器工具栏
        editor_toolbar = ttk.Frame(right_frame)
        editor_toolbar.pack(fill=X, pady=(0, 5))

        self.lbl_current_file = ttk.Label(editor_toolbar, text="未选择文件", font=("Helvetica", 9, "italic"))
        self.lbl_current_file.pack(side=LEFT, padx=5)

        ttk.Button(editor_toolbar, text="💾 保存本地", command=self.save_file, bootstyle=SUCCESS).pack(side=RIGHT, padx=5)

        # 文本编辑器主体
        self.text_editor = tk.Text(
            right_frame, 
            wrap=tk.WORD, 
            font=("Consolas", 11), 
            undo=True, 
            bg="#1e1e1e", 
            fg="#d4d4d4",
            insertbackground="white" # 光标颜色
        )
        self.text_editor.pack(fill=BOTH, expand=True)

        # 底栏: Git 操作区 & 日志框
        bottom_frame = ttk.Labelframe(self.root, text="Git 构建 & 上传控制台", padding=10)
        bottom_frame.pack(fill=X, padx=10, pady=(5, 10))

        # 工具条 (Commit 输入框 + 运行按钮)
        action_bar = ttk.Frame(bottom_frame)
        action_bar.pack(fill=X, pady=(0, 5))

        ttk.Label(action_bar, text="Commit 信息:").pack(side=LEFT, padx=(0, 5))
        self.commit_msg_entry = ttk.Entry(action_bar, width=35)
        self.commit_msg_entry.insert(0, "Auto update blog")
        self.commit_msg_entry.pack(side=LEFT, padx=5)

        # 核心一键部署按钮 (整合 BAT 逻辑)
        self.btn_push = ttk.Button(
            action_bar, 
            text="🚀 一键提交并推送 (Auto Push)", 
            command=self.start_git_push_thread, 
            bootstyle=DANGER
        )
        self.btn_push.pack(side=RIGHT, padx=5)

        # 运行日志终端框
        self.log_box = tk.Text(
            bottom_frame, 
            height=6, 
            bg="#0d1117", 
            fg="#00ff66", 
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.log_box.pack(fill=X, expand=True)
        self.log("就绪。准备执行构建或推送任务。")

    def log(self, message):
        """向日志终端追加文本"""
        self.log_box.insert(tk.END, f"{message}\n")
        self.log_box.see(tk.END)

    def browse_folder(self):
        """选择 Quartz 项目根目录"""
        folder = filedialog.askdirectory(title="选择 Quartz 项目根路径")
        if folder:
            self.quartz_path.set(folder)
            self.load_markdown_files()

    def load_markdown_files(self):
        """扫描 content 目录下的所有 .md 文件并渲染树状结构"""
        base_dir = self.quartz_path.get()
        if not base_dir or not os.path.exists(base_dir):
            messagebox.showerror("错误", "请先选择有效的 Quartz 根目录！")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)

        content_dir = os.path.join(base_dir, "content")
        target_dir = content_dir if os.path.exists(content_dir) else base_dir

        def add_nodes(parent, path):
            try:
                for entry in sorted(os.listdir(path)):
                    full_path = os.path.join(path, entry)
                    if os.path.isdir(full_path):
                        if entry in ['.git', 'node_modules', '.quartz']:
                            continue
                        node = self.tree.insert(parent, "end", text=f"📁 {entry}", open=False)
                        add_nodes(node, full_path)
                    elif entry.endswith(".md"):
                        self.tree.insert(parent, "end", text=f"📄 {entry}", values=(full_path,))
            except PermissionError:
                pass

        root_node = self.tree.insert("", "end", text=os.path.basename(target_dir), open=True)
        add_nodes(root_node, target_dir)
        self.log(f"已加载文章列表：{target_dir}")

    def on_file_selected(self, event):
        """选中左侧列表的文件时，载入内容到右侧编辑器"""
        selected_items = self.tree.selection()
        if not selected_items:
            return

        item = selected_items[0]
        values = self.tree.item(item, "values")

        if values:
            file_path = values[0]
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                self.text_editor.delete("1.0", tk.END)
                self.text_editor.insert("1.0", content)
                self.current_file_path = file_path
                self.lbl_current_file.config(text=f"当前正在编辑: {os.path.basename(file_path)}")
            except Exception as e:
                messagebox.showerror("读取错误", f"无法打开文件: {e}")

    def save_file(self):
        """保存编辑器内容到本地 markdown 文件"""
        if not self.current_file_path:
            messagebox.showwarning("警告", "请先在左侧选择要保存的文件！")
            return

        content = self.text_editor.get("1.0", tk.END)
        try:
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(content.rstrip() + "\n")
            self.log(f"💾 文件已保存: {os.path.basename(self.current_file_path)}")
            messagebox.showinfo("成功", "文件保存成功！")
        except Exception as e:
            messagebox.showerror("保存失败", f"写入文件出现错误: {e}")

    def start_git_push_thread(self):
        """使用线程启动 Git 逻辑，防止 GUI 卡死"""
        threading.Thread(target=self.run_bat_push_logic, daemon=True).start()

    def run_bat_push_logic(self):
        """完全对应批处理 (BAT) 逻辑的 Python 实现"""
        repo_path = self.quartz_path.get()
        if not repo_path or not os.path.exists(os.path.join(repo_path, ".git")):
            messagebox.showerror("Git 错误", "指定的 Quartz 路径不是有效的 Git 仓库！")
            return

        commit_msg = self.commit_msg_entry.get().strip() or "Auto update blog"

        # 禁用按钮防止重复点击
        self.btn_push.config(state=DISABLED, text="⌛ 推送中...")
        
        try:
            repo = Repo(repo_path)

            # [1/3] Adding changes...
            self.log("\n[1/3] Adding changes...")
            repo.git.add(A=True)

            # [2/3] Committing changes...
            self.log(f"[2/3] Committing changes with msg: '{commit_msg}'...")
            if repo.is_dirty(index=True, working_tree=True):
                repo.index.commit(commit_msg)
            else:
                self.log("ℹ️  没有发现新改动/新文件，跳过 commit 阶段...")

            # [3/3] Pushing to GitHub...
            self.log("[3/3] Pushing to GitHub (origin/main)...")
            origin = repo.remote(name='origin')
            push_info = origin.push(refspec='main:main')

            self.log("\n====================================")
            self.log(" Success! Cloudflare is building.")
            self.log("====================================\n")
            
            messagebox.showinfo("成功", "推送完成！Cloudflare Pages 已收到通知并开始自动构建部署。")

        except GitCommandError as g_err:
            self.log(f"\n❌ Git 执行错误: {g_err}")
            messagebox.showerror("Git 错误", f"提交或推送失败:\n{g_err}")
        except Exception as e:
            self.log(f"\n❌ 未知异常: {e}")
            messagebox.showerror("错误", f"发生异常: {e}")
        finally:
            # 恢复按钮状态
            self.btn_push.config(state=NORMAL, text="🚀 一键提交并推送 (Auto Push)")

if __name__ == "__main__":
    app_root = ttk.Window(themename="darkly")
    app = QuartzEditorApp(app_root)
    app_root.mainloop()