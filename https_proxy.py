import socket
from datetime import datetime
from threading import Thread

listen_addr = ('localhost', 7777)

listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
listener.bind(listen_addr)


def listen_start():
    append_log('Start listen')
    listener.listen(20)

    while True:
        client, addr = listener.accept()
        header_recver = Thread(target=recv_header, args=[client])
        header_recver.setDaemon(True)
        header_recver.start()


def recv_header(client):
    service = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        header = client.recv(1024).decode()
        headerItems = header.split('\r\n')
        typeIndex = headerItems[0].find('CONNECT')
        if typeIndex < 0:
            return

        host = headerItems[0][typeIndex+8:].split(':')[0]
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
    with open('log.txt', 'a') as f:
        f.write(dt + '|' + msg + '\n')


if __name__ == '__main__':
    listen_start()
