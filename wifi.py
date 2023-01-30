import network
import time
import gc

class Wifi():
    def __init__(self, ssid : str, password : str):
        self.ssid = ssid
        self._password = password
        self._wlan : network.WLAN
        self.ipaddress : str

    def start(self):
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)
        self._wlan.connect(self.ssid, self._password)

        # Wait for connect or fail
        max_wait = 10
        while max_wait > 0:
            if self._wlan.status() < 0 or self._wlan.status() >= 3:
                break
            max_wait -= 1
            print('-- waiting for connection...')
            time.sleep(1)

        # Handle connection error
        if self._wlan.status() != 3:
            raise RuntimeError('-- network connection failed')
        else:
            print('-- wifi connected')
            status = self._wlan.ifconfig()
            self.ipaddress = status[0]
            print( '-- ip = ' + self.ipaddress )

    def status(self):
        return self._wlan.status()
    
    def shutdown(self):
        self._wlan.disconnect()

    def __del__(self):
        self._wlan.active(False)
        self._wlan.disconnect()

if __name__ == "__main__":
    from secrets import wifi as wifi_secrets
    
    print('wifi.py main')
    ssid = wifi_secrets['ssid']
    password = wifi_secrets['password']

    wifi = Wifi(ssid,password)
    wifi.start()
    print(wifi.ipaddress)
    print(wifi.status())
    del wifi
    gc.enable()
    gc.collect()
    time.sleep(5)