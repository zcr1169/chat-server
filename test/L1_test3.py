import socket

alice = socket.socket()
alice.connect(("localhost", 8888))
bob = socket.socket()
bob.connect(("localhost", 8888))

alice.sendall(b"LOGIN CHAT/1.0\r\nUser: alice\r\nContent-Length: 0\r\n\r\n")
print("alice login:", alice.recv(4096).decode(errors="replace"))
bob.sendall(b"LOGIN CHAT/1.0\r\nUser: bob\r\nContent-Length: 0\r\n\r\n")
print("bob login:", bob.recv(4096).decode(errors="replace"))

req1 = "MSG CHAT/1.0\r\nContent-Length: 3\r\n\r\none"
req2 = "MSG CHAT/1.0\r\nContent-Length: 3\r\n\r\ntwo"
req3 = "MSG CHAT/1.0\r\nContent-Length: 5\r\n\r\nthree"

alice.sendall((req1 + req2 + req3).encode())

print("alice responses:", alice.recv(4096).decode(errors="replace"))
print("bob relayed:", bob.recv(4096).decode(errors="replace"))

# 期望：bob应收到3条独立消息 onetwothree，而不是粘在一起
