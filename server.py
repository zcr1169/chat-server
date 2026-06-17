#!/usr/bin/env python3
"""
CHAT/1.0 聊天服务器
支持: L1 基础功能 + L2 私聊与群组 + E2 消息加密
协议参考: CHAT/1.0 (仿HTTP/1.1格式)
"""

import socket
import threading
import re
import sys
import time


# ─── 常量 ────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8888


class ChatServer:
    """基于TCP的多线程聊天服务器"""

    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}       # username -> socket
        self.keys = {}          # username -> encryption key
        self.groups = {}        # group_name -> set(username)
        self.lock = threading.Lock()

    # ─── XOR 加密/解密 ─────────────────────────────────────

    @staticmethod
    def xor_crypt(data, key):
        """XOR 加密/解密（对称）"""
        key_bytes = key.encode('utf-8')
        return bytes([d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data)])

    # ─── 启动 ────────────────────────────────────────────────

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"[Server] 监听 {self.host}:{self.port}")
        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                print(f"[Server] 新连接: {addr}")
                t = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, addr),
                    daemon=True,
                )
                t.start()
        except KeyboardInterrupt:
            print("\n[Server] 关闭")
        finally:
            self.server_socket.close()

    # ─── 协议工具方法 ────────────────────────────────────────

    @staticmethod
    def response(code, reason):
        """构造不含body的响应"""
        return f"CHAT/1.0 {code} {reason}\r\nContent-Length: 0\r\n\r\n".encode()

    @staticmethod
    def response_body(code, reason, body_bytes):
        """构造含body的响应"""
        return (
            f"CHAT/1.0 {code} {reason}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode() + body_bytes

    def relay(self, from_user, body):
        """构造 202 MSG_RELAYED 中继消息（明文）"""
        return (
            f"CHAT/1.0 202 MSG_RELAYED\r\n"
            f"From: {from_user}\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

    def relay_enc(self, from_user, body, target_user):
        """构造 202 MSG_RELAYED 中继消息（用目标用户的 key 加密）"""
        with self.lock:
            target_key = self.keys.get(target_user, "")
        if target_key:
            enc_body = self.xor_crypt(body, target_key)
            return (
                f"CHAT/1.0 202 MSG_RELAYED\r\n"
                f"From: {from_user}\r\n"
                f"Encryption: xor\r\n"
                f"Content-Length: {len(enc_body)}\r\n\r\n"
            ).encode() + enc_body
        return self.relay(from_user, body)

    # ─── 广播用户列表 ────────────────────────────────────────

    def notify_user_list(self, exclude=None):
        """向所有在线用户发送最新的用户列表 (201 USERLIST)，排除指定用户"""
        with self.lock:
            user_list = ",".join(self.clients.keys()).encode()
        resp = self.response_body(201, "USERLIST", user_list)
        with self.lock:
            targets = {u: s for u, s in self.clients.items() if u != exclude}

        def _send():
            time.sleep(0.3)
            for sock in targets.values():
                try:
                    sock.sendall(resp)
                except Exception:
                    pass

        threading.Thread(target=_send, daemon=True).start()

    # ─── 命令处理 ────────────────────────────────────────────

    def handle_login(self, headers, state):
        """处理 LOGIN 命令"""
        if state["user"]:
            return self.response(400, "BAD_REQUEST")

        username = headers.get("User", "")
        if not re.match(r"^[a-zA-Z0-9_]{1,20}$", username):
            return self.response(400, "BAD_REQUEST")

        # E2: Key 头可选，有则加密，无则明文
        key = headers.get("Key", "")

        with self.lock:
            if username in self.clients:
                return self.response(409, "USERNAME_TAKEN")
            self.clients[username] = state["sock"]
            self.keys[username] = key

        state["user"] = username
        self.notify_user_list(exclude=username)
        return self.response(200, "OK")

    def handle_msg(self, headers, body, state):
        """处理 MSG 命令 —— 广播 / 私聊 / 群组"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")

        to = headers.get("To", "")
        username = state["user"]

        # E2: 判断原始消息是否加密
        was_encrypted = headers.get("Encryption") == "xor"

        # E2: 如果客户端发了 Encryption 头，先用发送者的 key 解密
        if was_encrypted:
            with self.lock:
                sender_key = self.keys.get(username, "")
            if sender_key:
                body = self.xor_crypt(body, sender_key)

        # E2: 加密消息不能发给没有Key的用户
        if was_encrypted:
            if to.startswith("#"):
                group_name = to[1:]
                with self.lock:
                    if group_name not in self.groups:
                        return self.response(404, "GROUP_NOT_FOUND")
                    members = self.groups[group_name].copy()
                for m in members:
                    if m != username and not self.keys.get(m, ""):
                        return self.response(400, "BAD_REQUEST")
            elif to:
                with self.lock:
                    target_key = self.keys.get(to, "")
                if not target_key:
                    return self.response(400, "BAD_REQUEST")
            else:
                with self.lock:
                    for u in self.clients:
                        if u != username and not self.keys.get(u, ""):
                            return self.response(400, "BAD_REQUEST")

        # --- 群组消息 ---
        if to.startswith("#"):
            group_name = to[1:]
            with self.lock:
                if group_name not in self.groups:
                    return self.response(404, "GROUP_NOT_FOUND")
                if username not in self.groups[group_name]:
                    return self.response(403, "NOT_GROUP_MEMBER")
                members = self.groups[group_name].copy()

            with self.lock:
                for m in members:
                    if m != username and m in self.clients:
                        try:
                            if was_encrypted:
                                self.clients[m].sendall(self.relay_enc(username, body, m))
                            else:
                                self.clients[m].sendall(self.relay(username, body))
                        except Exception:
                            pass
            return self.response(200, "OK")

        # --- 私聊 ---
        if to:
            with self.lock:
                if to not in self.clients:
                    return self.response(404, "USER_NOT_FOUND")
                target = self.clients[to]

            msg = self.relay_enc(username, body, to) if was_encrypted else self.relay(username, body)
            try:
                target.sendall(msg)
            except Exception:
                pass
            return self.response(200, "OK")

        # --- 广播 ---
        with self.lock:
            targets = {u: s for u, s in self.clients.items() if u != username}
        for u, sock in targets.items():
            try:
                if was_encrypted:
                    sock.sendall(self.relay_enc(username, body, u))
                else:
                    sock.sendall(self.relay(username, body))
            except Exception:
                pass
        return self.response(200, "OK")

    def handle_list(self, state):
        """处理 LIST 命令"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")
        with self.lock:
            user_list = ",".join(self.clients.keys()).encode()
        return self.response_body(201, "USERLIST", user_list)

    def handle_logout(self, state):
        """处理 LOGOUT 命令"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")

        with self.lock:
            self.clients.pop(state["user"], None)
            self.keys.pop(state["user"], None)

        resp = self.response(200, "OK")
        state["user"] = None
        self.notify_user_list()
        return resp

    def handle_create_group(self, headers, state):
        """处理 CREATEGROUP 命令"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")

        group = headers.get("Group", "")
        if not group:
            return self.response(400, "BAD_REQUEST")

        with self.lock:
            if group in self.groups:
                return self.response(409, "GROUP_EXISTS")
            self.groups[group] = {state["user"]}

        return self.response(200, "OK")

    def handle_join_group(self, headers, state):
        """处理 JOINGROUP 命令"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")

        group = headers.get("Group", "")
        if not group:
            return self.response(400, "BAD_REQUEST")

        with self.lock:
            if group not in self.groups:
                return self.response(404, "GROUP_NOT_FOUND")
            self.groups[group].add(state["user"])

        return self.response(200, "OK")

    def handle_file(self, headers, body, state):
        """处理 FILE 命令 - 文件传输"""
        if not state["user"]:
            return self.response(401, "NOT_LOGGED_IN")

        to = headers.get("To", "")
        username = state["user"]

        # 构造文件转发报文
        file_header = (
            f"CHAT/1.0 202 FILE_RELAYED\r\n"
            f"From: {username}\r\n"
            f"Filename: {headers.get('Filename', 'unknown')}\r\n"
            f"Content-Type: {headers.get('Content-Type', 'application/octet-stream')}\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode() + body

        if to.startswith("#"):
            # 群组文件
            group_name = to[1:]
            with self.lock:
                if group_name not in self.groups:
                    return self.response(404, "GROUP_NOT_FOUND")
                if username not in self.groups[group_name]:
                    return self.response(403, "NOT_GROUP_MEMBER")
                members = self.groups[group_name].copy()
            with self.lock:
                for m in members:
                    if m != username and m in self.clients:
                        try:
                            self.clients[m].sendall(file_header)
                        except Exception:
                            pass
            return self.response(200, "OK")

        elif to:
            # 私聊文件
            with self.lock:
                if to not in self.clients:
                    return self.response(404, "USER_NOT_FOUND")
                target = self.clients[to]
            try:
                target.sendall(file_header)
            except Exception:
                pass
            return self.response(200, "OK")

        else:
            # 广播文件
            with self.lock:
                targets = {u: s for u, s in self.clients.items() if u != username}
            for sock in targets.values():
                try:
                    sock.sendall(file_header)
                except Exception:
                    pass
            return self.response(200, "OK")

    # ─── 客户端处理主循环 ────────────────────────────────────

    def handle_client(self, sock, addr):
        """处理一个客户端连接（含TCP粘包/拆包）"""
        state = {"user": None, "sock": sock}
        buf = b""

        try:
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                buf += data

                # 期望的 body 完整长度（-1 表示还没解析到）
                expected_total = -1

                # 循环解析 buffer 中的完整消息
                while True:
                    # 如果正在等待 body 数据
                    if expected_total > 0:
                        if len(buf) < expected_total:
                            break  # body 不完整，等更多数据
                        body = buf[header_start:expected_total]
                        buf = buf[expected_total:]
                        expected_total = -1

                        # 分发命令
                        command = parts[0]

                        if command == "LOGIN":
                            resp = self.handle_login(headers, state)
                        elif command == "MSG":
                            resp = self.handle_msg(headers, body, state)
                        elif command == "LIST":
                            resp = self.handle_list(state)
                        elif command == "LOGOUT":
                            resp = self.handle_logout(state)
                            sock.sendall(resp)
                            return
                        elif command == "CREATEGROUP":
                            resp = self.handle_create_group(headers, state)
                        elif command == "JOINGROUP":
                            resp = self.handle_join_group(headers, state)
                        elif command == "FILE":
                            resp = self.handle_file(headers, body, state)
                        else:
                            resp = self.response(400, "BAD_REQUEST")

                        sock.sendall(resp)
                        continue

                    # 1. 找到 \r\n\r\n (头部结束)
                    idx = buf.find(b"\r\n\r\n")
                    if idx == -1:
                        break  # 头部不完整，等更多数据

                    # 2. 解析头部
                    header_text = buf[:idx].decode("utf-8", errors="replace")
                    lines = header_text.split("\r\n")
                    first_line = lines[0]

                    # 3. 校验协议格式: "COMMAND CHAT/1.0"
                    parts = first_line.split(" ")
                    if len(parts) != 2 or parts[1] != "CHAT/1.0":
                        buf = buf[idx + 4:]
                        try:
                            sock.sendall(self.response(400, "BAD_REQUEST"))
                        except Exception:
                            pass
                        continue

                    headers = {}
                    for line in lines[1:]:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            headers[k.strip()] = v.strip()

                    # 4. 校验 Content-Length
                    cl_str = headers.get("Content-Length", "")
                    if not cl_str or not cl_str.isdigit():
                        buf = buf[idx + 4:]
                        try:
                            sock.sendall(self.response(400, "BAD_REQUEST"))
                        except Exception:
                            pass
                        continue

                    content_length = int(cl_str)
                    total = idx + 4 + content_length

                    # 5. body 是否完整
                    if len(buf) < total:
                        expected_total = total
                        header_start = idx + 4
                        break  # 等更多数据，不再搜索 \r\n\r\n

                    body = buf[idx + 4 : total]
                    buf = buf[total:]

                    # 6. 分发命令
                    command = parts[0]

                    if command == "LOGIN":
                        resp = self.handle_login(headers, state)
                    elif command == "MSG":
                        resp = self.handle_msg(headers, body, state)
                    elif command == "LIST":
                        resp = self.handle_list(state)
                    elif command == "LOGOUT":
                        resp = self.handle_logout(state)
                        sock.sendall(resp)
                        return
                    elif command == "CREATEGROUP":
                        resp = self.handle_create_group(headers, state)
                    elif command == "JOINGROUP":
                        resp = self.handle_join_group(headers, state)
                    elif command == "FILE":
                        resp = self.handle_file(headers, body, state)
                    else:
                        resp = self.response(400, "BAD_REQUEST")

                    sock.sendall(resp)

        except Exception as e:
            print(f"[Server] 错误 {addr}: {e}")
        finally:
            # 清理: 如果用户还在线就移除
            if state["user"]:
                with self.lock:
                    self.clients.pop(state["user"], None)
                    self.keys.pop(state["user"], None)
                self.notify_user_list()
            sock.close()
            print(f"[Server] 断开: {addr}")


# ─── 启动入口 ────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = ChatServer(port=port)
    server.start()
