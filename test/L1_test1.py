import socket
import time

def recv_print(name, sock):
    data = sock.recv(4096)
    print(name, data.decode(errors="replace"))

alice = socket.socket()
alice.connect(("localhost", 8888))
bob = socket.socket()
bob.connect(("localhost", 8888))

alice.sendall(b"LOGIN CHAT/1.0\r\nUser: alice\r\nContent-Length: 0\r\n\r\n")
recv_print("alice login:", alice)
bob.sendall(b"LOGIN CHAT/1.0\r\nUser: bob\r\nContent-Length: 0\r\n\r\n")
recv_print("bob login:", bob)

body = b"Hello World!"
req = b"MSG CHAT/1.0\r\nContent-Length: " + str(len(body)).encode()
req += b"\r\n\r\n" + body
alice.sendall(req)
recv_print("alice msg response:", alice)
recv_print("bob relayed:", bob)

bob.sendall(b"LIST CHAT/1.0\r\nContent-Length: 0\r\n\r\n")
recv_print("bob list before logout:", bob)

alice.sendall(b"LOGOUT CHAT/1.0\r\nContent-Length: 0\r\n\r\n")
recv_print("alice logout:", alice)
alice.close()
time.sleep(0.2)

bob.sendall(b"LIST CHAT/1.0\r\nContent-Length: 0\r\n\r\n")
recv_print("bob list after alice logout:", bob)
bob.sendall(b"LOGOUT CHAT/1.0\r\nContent-Length: 0\r\n\r\n")
bob.close()