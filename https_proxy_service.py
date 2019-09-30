import socket
import json
import time
from datetime import datetime
from threading import Thread
import sys
import getopt

ip_version = 4
LISTEN_IPV4 = ('0.0.0.0', 8888)
LISTEN_IPV6 = ('::', 8889)
BUFFER_SIZE = 4096


class Proxy(object):

    def __init__(self):
        self.server_mode = 'vps'

    def run_proxy(self, mode):
        self.append_log('proxy start')
        self.server_mode = mode

        try:
            proxy_v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_v4.bind(LISTEN_IPV4)
            listener_v4 = Thread(target=self.proxy_listen, args=[proxy_v4])
            listener_v4.setDaemon(True)
            listener_v4.start()
        except Exception as ex:
            self.append_log(ex)

        try:
            proxy_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            proxy_v6.bind(LISTEN_IPV6)
            listener_v6 = Thread(target=self.proxy_listen, args=[proxy_v6])
            listener_v6.setDaemon(True)
            listener_v6.start()
        except Exception as ex:
            self.append_log(ex)

        hours = 1
        while True:
            time.sleep(3600)
            self.append_log('proxy run {0} hour(s)'.format(hours))
            hours += 1

    def proxy_listen(self, proxy):
        proxy.listen(10)
        while True:
            client, addr = proxy.accept()
            # self.append_log('connect to {0}:{1}'.format(addr[0], addr[1]))

            run_recv = Thread(target=self.recv_header, args=[client, addr])
            run_recv.setDaemon(True)
            run_recv.start()

    def check_auth(self, client, addr):
        try:
            if self.server_mode == 'local':
                if client.recv(1) == b'1':
                    client.sendall(b'1')
                    return client
            else:
                token = client.recv(50).decode().split(';_;_;')
                with open('config_proxy_auth.json', 'r') as f:
                    auth = json.load(f)
                for u in auth:
                    if u['name'] == token[0] and u['pwd'] == token[1]:
                        client.sendall(b'1')
                        return client
                client.sendall(b'0')
                client.close()
                self.append_log('{0}:{1} auth failed'.format(addr[0], addr[1]))
                return None
        except Exception as ex:
            self.append_log(ex)
            client.close()

    def recv_header(self, client, addr):
        try:
            client = self.check_auth(client, addr)
            if not client:
                return

            family = client.family
            if ip_version == 4:
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
                    self.append_log('host parsing failed')
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

        except Exception as ex:
            service.close()
            client.close()
            self.append_log(ex)

        bridge1 = Thread(target=self.bridge, args=[client, service])
        bridge2 = Thread(target=self.bridge, args=[service, client])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    def bridge(self, recver, sender):
        try:
            data = recver.recv(BUFFER_SIZE)
            while data:
                sender.sendall(data)
                data = recver.recv(BUFFER_SIZE)
        except Exception as ex:
            self.append_log(ex)
        finally:
            recver.close()
            sender.close()

    def append_log(self, msg):
        dt = str(datetime.now())
        # print(dt + ' | ' + msg)
        with open('proxy.log', 'a') as f:
            f.write('server | ' + dt + ' | ' + str(msg) + '\n')


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hi:', ['help', 'ipv='])
    except getopt.GetoptError:
        print('-i <ip version>')
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print('-i <input ip version>')
            sys.exit()
        if opt in ('-i', '--ipv'):
            ip_version = int(arg)

    Proxy().run_proxy('vps')
