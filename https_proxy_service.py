import socket
import json
import time
from datetime import datetime
from threading import Thread
import sys
import getopt

service_iptype = 4
listen_addr_ipv4 = ('0.0.0.0', 8888)
listen_addr_ipv6 = ('::', 8889)
BUFFER_SIZE = 4096


def listen_start():
    append_log('proxy start')
    try:
        proxy_v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_v4.bind(listen_addr_ipv4)
        listener_v4 = Thread(target=proxy_listen, args=[proxy_v4])
        listener_v4.setDaemon(True)
        listener_v4.start()
    except Exception as ex:
        append_log(str(ex))

    try:
        proxy_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        proxy_v6.bind(listen_addr_ipv6)
        listener_v6 = Thread(target=proxy_listen, args=[proxy_v6])
        listener_v6.setDaemon(True)
        listener_v6.start()
    except Exception as ex:
        append_log(str(ex))

    hours = 0
    while True:
        time.sleep(3600)
        append_log('proxy run {0} hour(s)'.format(hours))
        hours += 1


def proxy_listen(proxy):
    proxy.listen(10)
    while True:
        client, addr = proxy.accept()
        append_log('connect to {0}:{1}'.format(addr[0], addr[1]))

        checker = Thread(target=recv_header, args=[client, addr])
        checker.setDaemon(True)
        checker.start()


def check_auth(client, addr):
    try:
        token = client.recv(50).decode().split(';_;_;')
        with open('config_proxy_auth.json', 'r') as f:
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

        family = client.family
        if service_iptype == 4:
            family = socket.AF_INET
        service = socket.socket(family, socket.SOCK_STREAM)
        header = client.recv(BUFFER_SIZE).decode()
        header_items = header.split('\r\n')

        connect_index = header_items[0].find('CONNECT')
        if connect_index < 0:  # http proxy
            host_index = header.find('Host:')
            get_index = header.find('GET http')
            post_index = header.find('POST http')
            if host_index > -1:
                rn_index = header.find('\r\n', host_index)
                host = header[host_index+6:rn_index]
            elif get_index > -1 or post_index > -1:
                host = header.split('/')[2]
            else:
                client.close()
                append_log('host parsing failed')
                return

            host_items = host.split(':')
            host = host_items[0]
            if len(host_items) == 2:
                port = host_items[1]
            else:
                port = 80
            service.connect((host, int(port)))
            service.sendall(header.encode())

        else:  # https proxy
            host = header_items[0][connect_index+8:].split(':')[0]
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
        data = recver.recv(BUFFER_SIZE)
        while data:
            sender.sendall(data)
            data = recver.recv(BUFFER_SIZE)
    except Exception as ex:
        append_log(str(ex))
    finally:
        recver.close()
        sender.close()


def append_log(msg):
    dt = str(datetime.now())
    # print(dt + ' | ' + msg)
    with open('log_proxy.log', 'a') as f:
        f.write(dt + ' | ' + msg + '\n')


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:', ['help=', 'ipv='])
    except getopt.GetoptError:
        print('-i <ip version>')
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print('-i <input ip version')
            sys.exit()
        if opt in ('-i', '--ipv'):
            service_iptype = int(arg)
    listen_start()
