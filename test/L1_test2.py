import socket
import time

alice = socket.socket()
alice.connect(("localhost", 8888))
bob = socket.socket()
bob.connect(("localhost", 8888))

alice.sendall(b"LOGIN CHAT/1.0\r\nUser: alice\r\nContent-Length: 0\r\n\r\n")
print("alice login:", alice.recv(4096).decode(errors="replace"))
bob.sendall(b"LOGIN CHAT/1.0\r\nUser: bob\r\nContent-Length: 0\r\n\r\n")
print("bob login:", bob.recv(4096).decode(errors="replace"))

part1 = (
    "MSG CHAT/1.0\r\n"
    "Content-Length: 11\r\n"
    "\r\n"
    "hello"
).encode()
part2 = " world".encode()

alice.sendall(part1)
time.sleep(0.2)         # 模拟延迟
alice.sendall(part2)

print("alice response:", alice.recv(4096).decode(errors="replace"))
print("bob relayed:", bob.recv(4096).decode(errors="replace"))

# 期望：bob收到的body应该是 "hello world" 而不是只收到 "hello"
