def make_sock(context, sock_type, addr, bind):
    sock = context.socket(sock_type)
    if bind:
        sock.bind(addr)
    else:
        sock.connect(addr)
    return sock
