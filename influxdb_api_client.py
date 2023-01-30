import urequests
from time import sleep

from debug_print import print_, print_exception_

class Point:
    def __init__(self, measurement, tags, value):
        self.measurement = measurement
        self.tags = tags
        self.value = value
        
    def __str__(self):
        tagstring = ''
        for name,value in self.tags:
            tagstring += f',{name}={value}'
        return f'{self.measurement}{tagstring} value={self.value}' 
        
class InfluxApiClient:
    def __init__(self, url, organization, bucket, token):
        self.url = url
        self.organization = organization
        self.bucket = bucket
        self._token = token
        
    def write_data(self, points : list[Point]):
        headers = {
        'Authorization': f'Token {self._token}',
        'Content-Type': 'text/plain; charset=utf-8',
        'Accept': 'application/json'
        }
        request = self.url + '/api/v2/write?org=' + self.organization + '&bucket=' + self.bucket + '&precision=ns'
        data = '\n'.join(str(p) for p in points)

        #print_(headers)
        #print_(request)
        #print_(data)
        
        response = urequests.post(request, headers=headers, data=data)
        if response.status_code != 204:
            print_(f'influxdb write failed {response.status_code} : {response.reason}\n{response.text}')
        return response
    
    def write_with_retry(self, data : list[Point], tries : int, delay : int):
        attempts = 0
        success = False
        while not success and attempts < tries:
            try:
                attempts = attempts + 1
                self.write_data(data)
                success = True
                break
            except Exception as e:
                print_exception_(e)
                print_(f"Write failed, attempt {attempts} of {tries} waiting {delay}") # add signal strength if we find a faster way to getit
                sleep(delay)
        if not success:
            print_(f"data lost after {tries} retries")
            return False
        else:
            return True

if __name__ == "__main__":
    
    from wifi import Wifi

    from secrets import wifi as wifi_secrets
    from secrets import influxdb as influxdb_secrets
    
    ssid = wifi_secrets['ssid']
    password = wifi_secrets['password']

    wifi = Wifi(ssid,password)
    wifi.start()
    print_(wifi.ipaddress)
    print_(wifi.status())

    client = InfluxApiClient(influxdb_secrets['url'],influxdb_secrets['organization'],influxdb_secrets['bucket'],influxdb_secrets['token'])
    points = []
    points.append(Point("voltage",{('location','test'),('measurement','voltage'),('units','Volt')},6))
    points.append(Point("current",{('location','test'),('measurement','current'),('units','Amp')},.250))
    points.append(Point("power",{('location','test'),('measurement','power'),('units','Watt')},1.5))

    r = client.write_data(points)
    print_(r)
    print_(r.text)
    print_(r.content)
    print_(r.status_code)
    print_(r.reason)
    r.close()