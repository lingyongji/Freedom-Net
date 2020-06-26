import json
import socket
import sys
from datetime import datetime
from threading import Thread

from https_proxy_service import AIM_LOCAL, AIM_PROXY, BUFFER_SIZE, Proxy
from win_proxy_setting import back_proxy_config, set_proxy_config


class Client(object):

    def __init__(self):
        with open('config_client.json', 'r') as f:
            config = json.load(f)

        self.vps = config['vps']
        self.local_proxy_port = config['local_proxy_port']
        self.all_req_to_vps = config['all_req_to_vps']
        self.local_listener_port = config['local_listener_port']
        self.token = config['token'].encode()

    def run_client(self):
        set_proxy_config(self.local_listener_port)
        back = Thread(target=self.back_proxy_setting)
        back.setDaemon(True)
        back.start()

        run_client = Thread(target=self.client_listen)
        run_client.setDaemon(True)
        run_client.start()

        Proxy().run_proxy(AIM_LOCAL)

    def back_proxy_setting(self):
        input('input any key to exit\n')
        back_proxy_config()
        self.append_log('client closed')
        import os
        os._exit(0)

    def client_listen(self):
        self.append_log('client start')
        local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local.bind(('localhost', self.local_listener_port))
        local.listen(20)

        while True:
            client, addr = local.accept()

            req_send = Thread(target=self.send_request, args=[client])
            req_send.setDaemon(True)
            req_send.start()

    def send_request(self, client):
        request = client.recv(BUFFER_SIZE)
        if not request:
            client.close()
            return

        host = self.get_host(request.decode())
        if not host:
            client.close()
            return

        if bool(self.all_req_to_vps):
            proxy_aim = AIM_PROXY
        else:
            proxy_aim = self.check_aim(host.split(':')[0])
            if not proxy_aim:
                client.close()
                return

        proxy = self.connect_proxy(proxy_aim)
        if not proxy:
            client.close()
            self.append_log('connect proxy failed')
            return

        try:
            data = host.encode()
            proxy.sendall(data)
            if proxy.recv(1) == b'1':
                if host.split(':')[1] == '443':
                    client.sendall(
                        b'HTTP/1.0 200 Connection Established\r\n\r\n')
                else:
                    proxy.sendall(request)
                self.append_log('connect {0} OK'.format(host))
            else:
                proxy.close()
                client.close()
                self.append_log('connect {0} failed'.format(host))
                return

        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)
            client.close()
            proxy.close()
            return

        bridge1 = Thread(target=self.bridge, args=[
                         client, proxy, True, proxy_aim])
        bridge2 = Thread(target=self.bridge, args=[
                         proxy, client, False, proxy_aim])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    def get_host(self, header):
        try:
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
                    self.append_log('host parsing failed')

                host_items = host.split(':')
                host = host_items[0]
                if len(host_items) == 2:
                    port = host_items[1]
                else:
                    port = 80
            else:  # https proxy
                host = header_items[0][connect_index+8:].split(':')[0]
                port = 443
            return '{0}:{1}'.format(host, port)
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def check_aim(self, host):
        try:
            with open('host.txt', 'r') as f:
                for h in f:
                    if host.find(str(h).strip()) >= 0:
                        self.append_log('request {0} by proxy'.format(host))
                        return AIM_PROXY

            return AIM_LOCAL
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def connect_proxy(self, proxy_aim):
        try:
            if proxy_aim == AIM_LOCAL:
                proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                if proxy.connect_ex(('localhost', self.local_proxy_port)) == 0:
                    proxy.sendall(b'1')
                    if proxy.recv(1) == b'1':
                        return proxy
                    else:
                        proxy.close()
            else:
                for u in self.vps:
                    if bool(u['used']):
                        family = socket.AF_INET
                        if (u['ipv']) == 6:
                            family = socket.AF_INET6
                        proxy = socket.socket(family, socket.SOCK_STREAM)
                        if proxy.connect_ex((u['ip'], u['port'])) == 0:
                            proxy.sendall(self.token)
                            if proxy.recv(1) == b'1':
                                return proxy
                            else:
                                self.append_log(
                                    '{0} auth failed'.format(['ip']))
                                proxy.close()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

    def bridge(self, recver, sender, c_to_s, proxy_aim):
        try:
            while True:
                data = recver.recv(BUFFER_SIZE)
                if not data:
                    if c_to_s:
                        recver.close()
                        sender.close()
                    break
                sender.sendall(data)
        except Exception as ex:
            recver.close()
            sender.close()
            return

    def append_log(self, msg, func_name=''):
        dt = str(datetime.now())
        with open('log/{0}_proxy.log'.format(dt[0:10]), 'a') as f:
            f.write('{0} |C| {1} | {2} \n'.format(dt, str(msg), func_name))


if __name__ == '__main__':
    Client().run_client()
