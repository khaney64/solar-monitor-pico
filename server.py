import socket
from sys import print_exception
from status import Status
import _thread

class Request:
    def __init__(self, request : bytes):
        self.verb : str = ''
        self.requestline : str = ''
        self.command : str = ''
        self.parameters : dict[str,str] = {}
        self.headers : dict[str,str] = {}
        
        if len(request) > 0:
            lines = request.decode('utf-8').split('\r\n')
            parts = lines[0].split(' ')
            self.verb = parts[0]
            self.requestline = parts[1]
            parts = self.requestline.split('?')
            self.command = parts[0]
            if len(parts) > 1:
                params = parts[1].split('&')
                for nvps in params:
                    nvp = nvps.split('=')
                    if len(nvp) > 1:
                        self.parameters[nvp[0].lower()] = nvp[1].strip()
                    elif len(nvp) == 1:
                        self.parameters[nvp[0].lower()] = ''
            
            for header in range(1,len(lines)):
                parts = lines[header].split(':')
                if len(parts) > 1:
                    self.headers[parts[0]] = parts[1].strip()

class WebServer:
    def __init__(self, status : Status, port=80):
        # Open socket
        self.status = status
        self.addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
        self.port = port
 
        self._socket = socket.socket()
        self._socket.bind(self.addr)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.listen(1)
    
        print('-- listening on', self.addr)

    def listen(self, handler):
        html = """<!DOCTYPE html>
            <html>
                <head> <title>Solar Monitor</title><link rel="icon" href="./favicon.png"> </head>
                <body> <h1>Solar Monitor</h1>
                    <p>Status here</p>
                </body>
            </html>
        """
        try: 
            # Listen for connections
            cl = None
            while True:
                try:
                    cl, addr = self._socket.accept()
                    request = Request(cl.recv(1024))
                    
                    if 'favicon.png' in request.command:
                        with open("favicon.png", mode="rb") as favorite:
                            contents = favorite.read()
                        #print('content length',len(contents))
                        cl.send(f'HTTP/1.0 200 OK\r\nContent-type: image/png\r\nContent-Length: {len(contents)}\r\n\r\n')
                        cl.send(contents)

                    else:
                        print('-- client connected from', addr,request.verb,request.command)
                        response = html
                    
                        if handler != None:
                            handler(request, self.status)
            
                        cookie = "Set-Cookie: state=ready&location=test&delay=30; expires=Fri, 27-Dec-2023 10:57:36 GMT; Domain=192.168.86.24; Path=/"
                        cl.send(f'HTTP/1.0 200 OK\r\nContent-type: text/html\r\n{cookie}\r\n\r\n')
                        cl.send(response)

                    cl.close()

                except OSError as e:
                    print_exception(e)
                    if cl != None:
                        cl.close()
                        print('-- connection closed')
                        cl = None
                finally:
                    if cl != None:
                        cl.close()
                        cl = None

        except Exception as eouter:
            print('-- exception, closing socket',eouter)
            print_exception(eouter)
            self._socket.close()
        except KeyboardInterrupt as kbe:
            print('-- keyboard exception, closing socket',kbe)
            print_exception(kbe)
            self._socket.close()
            
    def shutdown(self):
        self._socket.close()    

if __name__ == "__main__":
    print('server.py main')
    from secrets import wifi as wifi_secrets
    
    ssid = wifi_secrets['ssid']
    password = wifi_secrets['password']

    from wifi import Wifi

    wifi = Wifi(ssid,password)
    wifi.start()
    print(wifi.ipaddress)
    print(wifi.status())

    status = Status(_thread.allocate_lock())

    server = WebServer(status)
    server.listen(lambda r : r.command)

    import time
    import gc
    gc.enable()
    gc.collect()
    del wifi
    time.sleep(5)