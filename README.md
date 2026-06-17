# CHAT/1.0 聊天系统

基于 Python socket 实现的自定义协议聊天室，支持 L1-L2 核心功能和 E1-E3 扩展功能。

## 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | 聊天服务器，支持多用户并发 |
| `client.py` | 终端客户端 |
| `gui_client.py` | 图形化客户端（tkinter） |
| `test/L1_test1.py` | L1 测试：登录、广播、列表、登出 |
| `test/L1_test2.py` | L1 测试：TCP 拆包（hello + world） |
| `test/L1_test3.py` | L1 测试：TCP 粘包（3条MSG一次发送） |

## 功能

### L1 - 基础聊天（30分）

- TCP 多线程服务器，端口 8888
- CHAT/1.0 协议解析（处理 TCP 粘包/拆包）
- LOGIN、MSG、LIST、LOGOUT 命令
- 消息广播转发
- 在线用户列表推送

### L2 - 私聊与群聊（25分）

- MSG + `To` 头部实现私聊
- CREATEGROUP、JOINGROUP 群组管理
- `To: #group_name` 群组消息路由

### E1 - 图形化客户端（10分）

- tkinter GUI 界面
- 登录界面、聊天主界面、在线用户列表
- 支持私聊、群聊、文件发送

### E2 - 消息加密（10分）

- LOGIN 时携带 `Key` 头部提交密钥
- MSG 时用 XOR 加密 body，添加 `Encryption: xor` 头部
- 服务器解密后用接收方密钥重新加密转发
- 接收方无密钥时服务器拒绝加密消息（400 BAD_REQUEST）

### E3 - 文件传输与表情（10分）

- FILE 命令传输任意文件
- 表情转换：`:smile:` → 😄、`:sad:` → 😢、`:like:` → 👍

## 运行方式

### 启动服务器

```bash
python server.py
```

### 终端客户端

```bash
python client.py              # 默认加密
python client.py --no-encrypt # 不加密
```

### GUI 客户端

```bash
python gui_client.py
```

登录时可选择是否启用加密。

### L1 测试脚本

先启动服务器，再运行测试脚本：

```bash
python server.py        # 终端1
python test/L1_test1.py # 终端2
```

## 客户端命令

```
login <名字>           登录
encrypt on/off         开关加密
msg <内容>             群发消息
msg @<用户> <内容>     私聊
msg #<群组> <内容>     群组消息
file <文件路径>        发送文件
list                   查看在线用户
group <群名>           创建群组
join <群名>            加入群组
logout                 登出
quit                   退出程序
```

## 技术要求

- Python 3.8+
- 仅使用标准库：socket、threading、re、sys、os、time、tkinter
- 禁止使用 Twisted、websockets、Flask-SocketIO 等第三方库
