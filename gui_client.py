#!/usr/bin/env python3
"""
CHAT/1.0 图形化客户端 (E1)
基于 tkinter，复用 client.py 的 CHAT/1.0 协议逻辑
"""

import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import os


class ChatGUI:
    """图形化聊天客户端"""

    def __init__(self):
        self.sock = None
        self.running = False
        self.username = None
        self.my_key = "mysecret"  # E2: 加密密钥

        # ── 主窗口 ──
        self.root = tk.Tk()
        self.root.title("CHAT/1.0 聊天客户端")
        self.root.geometry("700x500")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.build_login_frame()

    # ─── XOR 加密/解密 ──────────────────────────────────────

    @staticmethod
    def xor_crypt(data, key):
        key_bytes = key.encode('utf-8')
        return bytes([d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data)])

    # ─── E3 表情转换 ────────────────────────────────────────

    EMOJIS = {
        ":smile:": "😄",
        ":sad:": "😢",
        ":like:": "👍",
    }

    def replace_emojis(self, text):
        for code, emoji in self.EMOJIS.items():
            text = text.replace(code, emoji)
        return text

    # ══════════════════════════════════════════════════════════
    # 登录界面
    # ══════════════════════════════════════════════════════════

    def build_login_frame(self):
        self.login_frame = tk.Frame(self.root, padx=40, pady=40)
        self.login_frame.pack(expand=True)

        tk.Label(self.login_frame, text="CHAT/1.0 聊天客户端",
                 font=("Arial", 16, "bold")).pack(pady=(0, 20))

        # 用户名
        row1 = tk.Frame(self.login_frame)
        row1.pack(fill="x", pady=5)
        tk.Label(row1, text="用户名:", width=8, anchor="e").pack(side="left")
        self.entry_user = tk.Entry(row1, width=25)
        self.entry_user.pack(side="left", padx=5)
        self.entry_user.insert(0, "alice")

        # 服务器地址
        row2 = tk.Frame(self.login_frame)
        row2.pack(fill="x", pady=5)
        tk.Label(row2, text="服务器:", width=8, anchor="e").pack(side="left")
        self.entry_host = tk.Entry(row2, width=25)
        self.entry_host.pack(side="left", padx=5)
        self.entry_host.insert(0, "127.0.0.1")

        # 端口
        row3 = tk.Frame(self.login_frame)
        row3.pack(fill="x", pady=5)
        tk.Label(row3, text="端口:", width=8, anchor="e").pack(side="left")
        self.entry_port = tk.Entry(row3, width=25)
        self.entry_port.pack(side="left", padx=5)
        self.entry_port.insert(0, "8888")

        # 加密开关
        row4 = tk.Frame(self.login_frame)
        row4.pack(fill="x", pady=5)
        tk.Label(row4, text="加密:", width=8, anchor="e").pack(side="left")
        self.encrypt_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row4, text="启用消息加密 (E2)", variable=self.encrypt_var).pack(side="left", padx=5)

        # 登录按钮
        self.btn_login = tk.Button(self.login_frame, text="登录",
                                   font=("Arial", 12), width=15,
                                   command=self.do_login)
        self.btn_login.pack(pady=20)

    # ══════════════════════════════════════════════════════════
    # 聊天主界面
    # ══════════════════════════════════════════════════════════

    def build_chat_frame(self):
        self.login_frame.destroy()

        # 顶部状态栏
        top_bar = tk.Frame(self.root, bg="#4a90d9", height=30)
        top_bar.pack(fill="x")
        self.label_status = tk.Label(top_bar,
                                     text=f"已登录: {self.username}",
                                     bg="#4a90d9", fg="white",
                                     font=("Arial", 10))
        self.label_status.pack(side="left", padx=10)

        # 主区域：左边消息，右边用户列表
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # ── 左侧：消息区 ──
        left = tk.Frame(main_frame)
        left.pack(side="left", fill="both", expand=True)

        self.msg_area = scrolledtext.ScrolledText(left, state="disabled",
                                                  font=("Consolas", 10),
                                                  wrap="word")
        self.msg_area.pack(fill="both", expand=True)

        # ── 右侧：在线用户列表 ──
        right = tk.Frame(main_frame, width=150)
        right.pack(side="right", fill="y", padx=(5, 0))
        right.pack_propagate(False)

        tk.Label(right, text="在线用户", font=("Arial", 10, "bold")).pack(pady=5)
        self.user_list = tk.Listbox(right, font=("Arial", 10))
        self.user_list.pack(fill="both", expand=True)

        # ── 底部输入区 ──
        bottom = tk.Frame(self.root)
        bottom.pack(fill="x", padx=5, pady=5)

        # 聊天模式选择
        mode_frame = tk.Frame(self.root)
        mode_frame.pack(fill="x", padx=5)

        self.chat_mode = tk.StringVar(value="broadcast")
        tk.Radiobutton(mode_frame, text="群发", variable=self.chat_mode,
                       value="broadcast").pack(side="left")
        tk.Radiobutton(mode_frame, text="私聊", variable=self.chat_mode,
                       value="private").pack(side="left")
        tk.Radiobutton(mode_frame, text="群组", variable=self.chat_mode,
                       value="group").pack(side="left")

        tk.Label(mode_frame, text="目标:").pack(side="left", padx=(10, 0))
        self.entry_target = tk.Entry(mode_frame, width=15, font=("Arial", 10))
        self.entry_target.pack(side="left", padx=5)
        self.entry_target.insert(0, "")

        tk.Button(mode_frame, text="创建群组", font=("Arial", 9),
                  command=self.do_create_group).pack(side="left", padx=5)
        tk.Button(mode_frame, text="加入群组", font=("Arial", 9),
                  command=self.do_join_group).pack(side="left")
        tk.Button(mode_frame, text="发送文件", font=("Arial", 9),
                  command=self.do_send_file).pack(side="left", padx=5)

        # 输入框和按钮
        input_frame = tk.Frame(bottom)
        input_frame.pack(fill="x")

        # E2: 单条消息加密开关（没Key时禁用）
        self.msg_encrypt_var = tk.BooleanVar(value=bool(self.my_key))
        self.encrypt_check = tk.Checkbutton(input_frame, text="加密", variable=self.msg_encrypt_var)
        self.encrypt_check.pack(side="left")
        if not self.my_key:
            self.encrypt_check.config(state="disabled")

        self.entry_msg = tk.Entry(input_frame, font=("Arial", 11))
        self.entry_msg.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_msg.bind("<Return>", self.send_message)

        self.btn_send = tk.Button(input_frame, text="发送", font=("Arial", 10),
                                  width=8, command=self.send_message)
        self.btn_send.pack(side="right")

        self.btn_logout = tk.Button(input_frame, text="退出登录", font=("Arial", 10),
                                    width=8, command=self.do_logout)
        self.btn_logout.pack(side="right", padx=(0, 5))

    # ══════════════════════════════════════════════════════════
    # 协议逻辑（复用 client.py）
    # ══════════════════════════════════════════════════════════

    def send_request(self, command, headers=None, body=b""):
        """构造并发送 CHAT/1.0 请求"""
        if headers is None:
            headers = {}
        lines = [f"{command} CHAT/1.0\r\n"]
        for k, v in headers.items():
            lines.append(f"{k}: {v}\r\n")
        lines.append(f"Content-Length: {len(body)}\r\n")
        lines.append("\r\n")
        raw = "".join(lines).encode() + body
        self.sock.sendall(raw)

    def receive_loop(self):
        """持续接收服务器响应（后台线程）"""
        buf = b""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    self.root.after(0, self.append_msg, "[与服务器断开连接]")
                    self.running = False
                    break
                buf += data

                while True:
                    idx = buf.find(b"\r\n\r\n")
                    if idx == -1:
                        break

                    header_text = buf[:idx].decode("utf-8", errors="replace")
                    lines = header_text.split("\r\n")
                    first_line = lines[0]

                    headers = {}
                    for line in lines[1:]:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            headers[k.strip()] = v.strip()

                    content_length = int(headers.get("Content-Length", "0"))
                    total = idx + 4 + content_length
                    if len(buf) < total:
                        break

                    body = buf[idx + 4:total]
                    buf = buf[total:]

                    self.root.after(0, self.handle_response,
                                    first_line, headers, body)

            except Exception:
                if self.running:
                    self.root.after(0, self.append_msg, "[连接错误]")
                break

    def handle_response(self, first_line, headers, body):
        """解析服务器响应并更新界面"""
        parts = first_line.split(" ", 2)
        code = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""

        if code == "200":
            self.append_msg(f"[服务器] {reason}")

        elif code == "201":
            # 用户列表更新
            user_list = body.decode("utf-8", errors="replace")
            self.update_user_list(user_list)

        elif code == "202":
            from_user = headers.get("From", "???")
            # E3: 文件中继
            if "Filename" in headers:
                filename = headers.get("Filename", "unknown")
                save_path = os.path.join(".", filename)
                with open(save_path, "wb") as f:
                    f.write(body)
                self.append_msg(f"{from_user} 发送文件: {filename} (已保存)")
            else:
                msg = body.decode("utf-8", errors="replace")
                if headers.get("Encryption") == "xor":
                    msg = self.xor_crypt(body, self.my_key).decode("utf-8", errors="replace")
                # E3: 表情转换
                msg = self.replace_emojis(msg)
                self.append_msg(f"{from_user}: {msg}")

        elif code in ("400", "401", "403", "404", "409", "500"):
            self.append_msg(f"[错误 {code}] {reason}")

        else:
            self.append_msg(f"[服务器] {first_line}")

    # ══════════════════════════════════════════════════════════
    # 界面操作
    # ══════════════════════════════════════════════════════════

    def append_msg(self, text):
        """向消息区追加一行文字，自动滚动到底部"""
        self.msg_area.config(state="normal")
        self.msg_area.insert("end", text + "\n")
        self.msg_area.see("end")
        self.msg_area.config(state="disabled")

    def update_user_list(self, user_list_str):
        """更新在线用户列表"""
        self.user_list.delete(0, "end")
        for user in user_list_str.split(","):
            user = user.strip()
            if user:
                self.user_list.insert("end", user)

    def send_message(self, event=None):
        """点击发送或回车"""
        text = self.entry_msg.get().strip()
        if not text or not self.running:
            return
        self.entry_msg.delete(0, "end")

        # E3: 表情转换
        display_text = self.replace_emojis(text)

        mode = self.chat_mode.get()
        target = self.entry_target.get().strip()
        body = text.encode()

        if self.msg_encrypt_var.get() and self.my_key:
            enc_body = self.xor_crypt(body, self.my_key)
            enc_header = {"Encryption": "xor"}
        else:
            enc_body = body
            enc_header = {}

        if mode == "private":
            if not target:
                self.append_msg("[提示] 请输入私聊对象")
                return
            self.send_request("MSG", {"To": target, **enc_header}, enc_body)
            self.append_msg(f"我→{target}: {display_text}")

        elif mode == "group":
            if not target:
                self.append_msg("[提示] 请输入群组名")
                return
            self.send_request("MSG", {"To": f"#{target}", **enc_header}, enc_body)
            self.append_msg(f"我→#{target}: {display_text}")

        else:
            self.send_request("MSG", enc_header, enc_body)
            self.append_msg(f"我: {display_text}")

    def do_create_group(self):
        """创建群组"""
        name = self.entry_target.get().strip()
        if not name:
            self.append_msg("[提示] 请输入群组名")
            return
        self.send_request("CREATEGROUP", {"Group": name})
        self.append_msg(f"[创建群组] {name}")

    def do_join_group(self):
        """加入群组"""
        name = self.entry_target.get().strip()
        if not name:
            self.append_msg("[提示] 请输入群组名")
            return
        self.send_request("JOINGROUP", {"Group": name})
        self.append_msg(f"[加入群组] {name}")

    def do_send_file(self):
        """发送文件"""
        filepath = filedialog.askopenfilename(title="选择文件")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            file_data = f.read()
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif",
            ".txt": "text/plain", ".pdf": "application/pdf",
        }
        ct = content_types.get(ext, "application/octet-stream")
        self.send_request("FILE", {"Filename": filename, "Content-Type": ct}, file_data)
        self.append_msg(f"[文件] 已发送 {filename} ({len(file_data)} 字节)")

    # ══════════════════════════════════════════════════════════
    # 登录 / 登出
    # ══════════════════════════════════════════════════════════

    def do_login(self):
        """登录按钮"""
        self.username = self.entry_user.get().strip()
        host = self.entry_host.get().strip()
        port = self.entry_port.get().strip()

        if not self.username:
            messagebox.showwarning("提示", "请输入用户名")
            return

        try:
            port = int(port)
        except ValueError:
            messagebox.showwarning("提示", "端口号必须是数字")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.running = True
        except Exception as e:
            messagebox.showerror("连接失败", str(e))
            return

        # 发送 LOGIN（根据勾选决定是否带 Key）
        if self.encrypt_var.get():
            self.send_request("LOGIN", {"User": self.username, "Key": self.my_key})
        else:
            self.my_key = ""
            self.send_request("LOGIN", {"User": self.username})

        # 启动接收线程
        recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        recv_thread.start()

        # 切换到聊天界面
        self.build_chat_frame()

        # 主动请求一次在线用户列表
        self.send_request("LIST")

    def do_logout(self):
        """退出登录，回到登录界面"""
        if self.running:
            try:
                self.send_request("LOGOUT")
            except Exception:
                pass
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        # 清理聊天界面，回到登录
        self.root.winfo_children()[0].destroy()
        self.username = None
        self.sock = None
        self.build_login_frame()

    def on_close(self):
        """关闭窗口 = 退出程序"""
        if self.running:
            try:
                self.send_request("LOGOUT")
            except Exception:
                pass
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ─── 启动 ────────────────────────────────────────────────────
if __name__ == "__main__":
    app = ChatGUI()
    app.run()
