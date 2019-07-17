import socket
import json
from datetime import datetime
from threading import Thread

listen_addr = ('localhost', 8888)


def listen_start():
    append_log('proxy start')
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy.bind(listen_addr)
    proxy.listen(20)

    while True:
        client, addr = proxy.accept()
        append_log('connect to {0}:{1}'.format(addr[0], addr[1]))

        checker = Thread(target=recv_header, args=[client, addr])
        checker.setDaemon(True)
        checker.start()


def check_auth(client, addr):
    try:
        token = client.recv(50).decode().split(';_;_;')
        with open('auth.json', 'r') as f:
            auth = json.load(f)
        for u in auth:
            if u['name'] == token[0] and u['pwd'] == token[1]:
                client.sendall(b'1')
                return client
        client.sendall(b'0')
        client.close()
        append_log('{0}:{1} auth failed'.format(addr[0], addr[1]))
        return None
    except Exception as ex:
        append_log(str(ex))
        client.close()


def recv_header(auth_checker, addr):
    try:
        client = check_auth(auth_checker, addr)
        if not client:
            return

        header = client.recv(1024).decode()
        headerItems = header.split('\r\n')
        typeIndex = headerItems[0].find('CONNECT')
        if typeIndex < 0:
            return

        host = headerItems[0][typeIndex+8:].split(':')[0]
        service = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        service.connect((host, 443))
        client.sendall(b'HTTP/1.0 200 Connection Established\r\n\r\n')
        append_log('connect to [{0}]'.format(host))

        bridge1 = Thread(target=bridge, args=[client, service])
        bridge2 = Thread(target=bridge, args=[service, client])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    except Exception as ex:
        service.close()
        client.close()
        append_log(str(ex))


def bridge(recver, sender):
    try:
        data = recver.recv(1024)
        while data:
            sender.sendall(data)
            data = recver.recv(1024)
    except Exception as ex:
        append_log(str(ex))
    finally:
        recver.close()
        sender.close()
        append_log('bridge close')


def append_log(msg):
    dt = str(datetime.now())
    print(dt + '|' + msg)
    with open('proxy_log.txt', 'a') as f:
        f.write(dt + '|' + msg + '\n')


if __name__ == '__main__':
    listen_start()
