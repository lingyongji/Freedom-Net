#!/bin/sh

cd /root/
mkdir proxy
cd proxy/
mkdir log

cat >config_service.json<<EOF
{
	"v4_port": 443,
	"v6_port": 80,
	"tokens": ["admin_token", "user_token"]
}
EOF

cat >https_proxy_service.py<<EOF
import getopt
import json
import socket
import sys
import time
from datetime import datetime
from threading import Thread


BUFFER_SIZE = 4096
AIM_LOCAL = 1
AIM_PROXY = 2
ip_version = 4


class Proxy(object):

    def __init__(self):
        with open('config_service.json', 'r') as f:
            config = json.load(f)

        self.tokens = config['tokens']
        self.v4_port = config['v4_port']
        self.v6_port = config['v6_port']
        self.server_mode = AIM_PROXY

    def run_proxy(self, mode):
        self.append_log('proxy start')
        self.server_mode = mode

        try:
            proxy_v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_v4.bind(('0.0.0.0', self.v4_port))
            listener_v4 = Thread(target=self.proxy_listen, args=[proxy_v4])
            listener_v4.setDaemon(True)
            listener_v4.start()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

        try:
            proxy_v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            proxy_v6.bind(('::', self.v6_port))
            listener_v6 = Thread(target=self.proxy_listen, args=[proxy_v6])
            listener_v6.setDaemon(True)
            listener_v6.start()
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)

        hours = 1
        while True:
            time.sleep(3600)
            self.append_log('proxy run {0} hour(s)'.format(hours))
            hours += 1

    def proxy_listen(self, proxy):
        proxy.listen(20)
        while True:
            client, addr = proxy.accept()

            req_send = Thread(target=self.send_request, args=[client, addr])
            req_send.setDaemon(True)
            req_send.start()

    def send_request(self, client, addr):
        try:
            client = self.check_auth(client, addr)
            if not client:
                return

            family = client.family
            if ip_version == 4:
                family = socket.AF_INET
            service = socket.socket(family, socket.SOCK_STREAM)

            data = client.recv(BUFFER_SIZE)
            hostaddr = data.decode()
            host = hostaddr.split(':')[0]
            port = int(hostaddr.split(':')[1])
            if service.connect_ex((host, port)) == 0:
                client.sendall(b'1')
                self.append_log('connect {0} OK'.format(hostaddr))
            else:
                client.sendall(b'0')
                client.close()
                self.append_log('connect {0} failed'.format(hostaddr))
                return

        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)
            client.close()
            return

        bridge1 = Thread(target=self.bridge, args=[client, service, True])
        bridge2 = Thread(target=self.bridge, args=[service, client, False])
        bridge1.setDaemon(True)
        bridge2.setDaemon(True)
        bridge1.start()
        bridge2.start()

    def check_auth(self, client, addr):
        try:
            if self.server_mode == AIM_LOCAL:
                if client.recv(1) == b'1':
                    client.sendall(b'1')
                    return client
            else:
                token = client.recv(BUFFER_SIZE).decode()
                for t in self.tokens:
                    if t == token:
                        client.sendall(b'1')
                        return client
                client.close()
                self.append_log('{0}:{1} auth failed'.format(addr[0], addr[1]))
        except Exception as ex:
            self.append_log(ex, sys._getframe().f_code.co_name)
            client.close()

    def bridge(self, recver, sender, c_to_s):
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
            f.write('{0} |S| {1} | {2} \n'.format(dt, str(msg), func_name))


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

    Proxy().run_proxy(AIM_PROXY)
EOF

cat >run<<EOF
nohup python3 https_proxy_service.py > log.txt 2>&1 &
EOF

cat >run_ipv6<<EOF
nohup python3 https_proxy_service.py -i 6 > log.txt 2>&1 &
EOF

cat >stop<<EOF
eval $(ps -ef|grep "[0-9] python3 https_proxy_service.py"|awk '{print "kill "$2}')
EOF

bash run