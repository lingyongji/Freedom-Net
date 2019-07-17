import socket
import json
from datetime import datetime
from threading import Thread


def listen_start():
    append_log('start listen local')
    local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local.bind(('localhost', 7777))
    local.listen(20)

    while True:
        client, addr = local.accept()
        append_log('connect to {0}:{1}'.format(addr[0], addr[1]))

        header_recver = Thread(target=send_header, args=[client])
        header_recver.setDaemon(True)
        header_recver.start()


def check_auth():
    ok = False
    proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with open('config.json', 'r') as f:
            auth = json.load(f)
            for u in auth:
                if u['used']:
                    lg = '{0};_;_;{1}'.format(u['name'], u['pwd'])
                    proxy.connect((u['ip'], u['port']))
                    proxy.sendall(lg.encode())
                    if proxy.recv(1) == b'1':
                        return proxy
        return None
    except Exception as ex:
        append_log(str(ex))
        proxy.close()


def send_header(client):
    try:
        header = client.recv(1024)
        if not header:
            return

        proxy = check_auth()
        if not proxy:
            append_log('auth failed')
            return

        proxy.sendall(header)

        bridge1 = Thread(target=bridge, args=[client, proxy])
        bridge2 = Thread(target=bridge, args=[proxy, client])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    except Exception as ex:
        proxy.close()
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
    with open('client_log.txt', 'a') as f:
        f.write(dt + '|' + msg + '\n')


if __name__ == '__main__':
    listen_start()
