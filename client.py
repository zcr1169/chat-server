#!/usr/bin/env python3
"""
CHAT/1.0 聊天客户端
支持: L1 基础功能 + L2 私聊与群组
"""

import socket
import threading
import sys
import os


# ─── 常量 ────────────────────────────────────────────────────
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8888


class ChatClient:
    """基于TCP的聊天客户端"""

    def __init__(self, host=SERVER_HOST, port=SERVER_PORT):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = False
        self.my_key = ""  # E2: 加密密钥

    # ─── 连接 ────────────────────────────────────────────────

    def connect(self):
        self.sock.connect((self.host, self.port))
        self.running = True
        print(f"已连接到 {self.host}:{self.port}")

    # ─── XOR 加密/解密 ──────────────────────────────────────

    @staticmethod
    def xor_crypt(data, key):
        """XOR 加密/解密（对称）"""
        key_bytes = key.encode('utf-8')
        return bytes([d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data)])

    # ─── E3 表情转换 ────────────────────────────────────────

    EMOJIS = {
        ":smile:": "😄",
        ":sad:": "😢",
        ":like:": "👍",
        ":angry:": "😠",
        ":cool:": "😎",
        ":cry:": "😭",
        ":heart:": "❤️",
        ":star:": "⭐",
        ":fire:": "🔥",
        ":thumbsup:": "👍",
        ":wave:": "👋",
        ":clap:": "👏",
    }

    def replace_emojis(self, text):
        for code, emoji in self.EMOJIS.items():
            text = text.replace(code, emoji)
        return text

    # ─── 发送 CHAT/1.0 请求 ─────────────────────────────────

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

    # ─── 接收线程 ────────────────────────────────────────────

    def receive_loop(self):
        """持续接收并处理服务器响应"""
        buf = b""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    print("\n[与服务器断开连接]")
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

                    body = buf[idx + 4 : total]
                    buf = buf[total:]

                    self.handle_response(first_line, headers, body)

            except Exception as e:
                if self.running:
                    print(f"\n[错误: {e}]")
                break

    # ─── 处理服务器响应 ──────────────────────────────────────

    def handle_response(self, first_line, headers, body):
        """解析并显示服务器响应"""
        parts = first_line.split(" ", 2)
        code = parts[1] if len(parts) > 1 else ""
        reason = parts[2] if len(parts) > 2 else ""

        if code == "200":
            print(f"[服务器] {code} {reason}")
        elif code == "201":
            # 用户列表
            user_list = body.decode("utf-8", errors="replace")
            print(f"[在线用户] {user_list}")
        elif code == "202":
            from_user = headers.get("From", "???")
            # E3: 文件中继
            if "Filename" in headers:
                filename = headers.get("Filename", "unknown")
                save_path = os.path.join(".", filename)
                with open(save_path, "wb") as f:
                    f.write(body)
                print(f"  {from_user} 发送文件: {filename} (已保存到 {save_path})")
            else:
                # 普通消息中继
                msg = body.decode("utf-8", errors="replace")
                # E2: 如果有 Encryption 头，解密
                if headers.get("Encryption") == "xor" and self.my_key:
                    msg = self.xor_crypt(body, self.my_key).decode("utf-8", errors="replace")
                # E3: 表情转换
                msg = self.replace_emojis(msg)
                print(f"  {from_user}: {msg}")
        elif code in ("400", "401", "403", "404", "409", "500"):
            print(f"[错误 {code}] {reason}")
        else:
            print(f"[服务器] {first_line}")
            if body:
                print(f"  {body.decode('utf-8', errors='replace')}")

    # ─── 交互式命令循环 ──────────────────────────────────────

    def interactive(self):
        """读取用户输入并发送命令"""
        print()
        print("可用命令:")
        print("  login <名字>        登录")
        print("  encrypt on/off      开关加密")
        print("  msg <内容>          群发消息")
        print("  msg @<用户> <内容>  私聊")
        print("  msg #<群组> <内容>  群组消息")
        print("  file <文件路径>     发送文件")
        print("  list                查看在线用户")
        print("  group <群名>        创建群组")
        print("  join <群名>         加入群组")
        print("  logout              登出")
        print("  quit                退出程序")
        print()

        while self.running:
            try:
                line = input("> ").strip()
                if not line:
                    continue

                # ── login ──
                if line.startswith("login "):
                    username = line[6:].strip()
                    if self.my_key:
                        self.send_request("LOGIN", {"User": username, "Key": self.my_key})
                    else:
                        self.send_request("LOGIN", {"User": username})

                # ── list ──
                elif line == "list":
                    self.send_request("LIST")

                # ── encrypt on/off ──
                elif line.startswith("encrypt "):
                    val = line[8:].strip().lower()
                    if val == "on":
                        self.my_key = "mysecret"
                        print("[加密] 已开启")
                    elif val == "off":
                        self.my_key = ""
                        print("[加密] 已关闭")
                    else:
                        print("[提示] 用法: encrypt on / encrypt off")

                # ── msg (广播/私聊/群组) ──
                elif line.startswith("msg "):
                    content = line[4:].strip()
                    # E3: 表情转换
                    content = self.replace_emojis(content)
                    if content.startswith("@"):
                        parts = content[1:].split(" ", 1)
                        to_user = parts[0]
                        body = parts[1].encode() if len(parts) > 1 else b""
                        if self.my_key:
                            enc_body = self.xor_crypt(body, self.my_key)
                            self.send_request("MSG", {"To": to_user, "Encryption": "xor"}, enc_body)
                        else:
                            self.send_request("MSG", {"To": to_user}, body)
                    elif content.startswith("#"):
                        parts = content.split(" ", 1)
                        to_group = parts[0]
                        body = parts[1].encode() if len(parts) > 1 else b""
                        if self.my_key:
                            enc_body = self.xor_crypt(body, self.my_key)
                            self.send_request("MSG", {"To": to_group, "Encryption": "xor"}, enc_body)
                        else:
                            self.send_request("MSG", {"To": to_group}, body)
                    else:
                        body = content.encode()
                        if self.my_key:
                            enc_body = self.xor_crypt(body, self.my_key)
                            self.send_request("MSG", {"Encryption": "xor"}, enc_body)
                        else:
                            self.send_request("MSG", {}, body)

                # ── group (创建群组) ──
                elif line.startswith("group "):
                    group_name = line[6:].strip()
                    self.send_request("CREATEGROUP", {"Group": group_name})

                # ── join (加入群组) ──
                elif line.startswith("join "):
                    group_name = line[5:].strip()
                    self.send_request("JOINGROUP", {"Group": group_name})

                # ── file (发送文件) ──
                elif line.startswith("file "):
                    filepath = line[5:].strip()
                    if not os.path.exists(filepath):
                        print(f"[提示] 文件不存在: {filepath}")
                        continue
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
                    self.send_request("FILE", {
                        "Filename": filename,
                        "Content-Type": ct,
                    }, file_data)
                    print(f"[文件] 已发送 {filename} ({len(file_data)} 字节)")

                # ── logout ──
                elif line == "logout":
                    self.send_request("LOGOUT")

                # ── quit ──
                elif line == "quit":
                    self.running = False
                    break

                else:
                    print("[提示] 未知命令，请输入 login/msg/list/group/join/logout/quit")

            except (EOFError, KeyboardInterrupt):
                break

        self.sock.close()
        print("再见！")

    # ─── 主入口 ──────────────────────────────────────────────

    def run(self):
        self.connect()
        # 启动接收线程
        recv_thread = threading.Thread(target=self.receive_loop, daemon=True)
        recv_thread.start()
        # 交互循环（主线程）
        self.interactive()


# ─── 启动入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else SERVER_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else SERVER_PORT
    encrypt = "--no-encrypt" not in sys.argv
    client = ChatClient(host=host, port=port)
    if not encrypt:
        client.my_key = ""
    client.run()
