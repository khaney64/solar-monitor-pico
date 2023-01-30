import time
import _thread
from influxdb_api_client import InfluxApiClient
from secrets import influxdb as influxdb_secrets
import machine

class Data:
    def __init__(self, timestamp, voltage : float, current : float, power : float, temperature : float):
        self.timestamp = timestamp
        self.voltage = voltage
        self.current = current
        self.power = power
        self.temperature = temperature

class Status:
    def __init__(self, _lock : _thread.LockType, location : str = 'test', delay : int = 30, state : str = 'waiting'):
        self.lock = _lock
        self.location = location
        self.delay = delay
        self.state = state
        self.foo = time.localtime()
        self.starttime = time.localtime()
        self.endtime = time.localtime()
        self.data = {}
        self.data_count = 0
        self.influxdbclient = InfluxApiClient(influxdb_secrets['url'],influxdb_secrets['organization'],influxdb_secrets['bucket'],influxdb_secrets['token'])
        
    def update_config(self, location, delay):
        self.lock.acquire()
        self.location = location
        self.delay = delay
        self.lock.release()
        
    def update_state(self, state):
        self.lock.acquire()
        self.state = state
        self.lock.release()
        
    def record_data(self, timestamp, voltage : float, current : float, power : float, temperature : float):
        self.lock.acquire()
        self.data[time.mktime(timestamp)] = Data(timestamp, voltage, current, power, temperature)
        self.data_count += 1
        self.lock.release()
        
    def get_state(self) -> str:
        self.lock.acquire()
        state = self.state
        self.lock.release()
        return state

    def get_config(self) -> tuple[str,int]:
        self.lock.acquire()
        location = self.location
        delay = self.delay
        self.lock.release()
        return location, delay
    
    def get_data(self, clear=False) -> dict:
        self.lock.acquire()
        data = self.data
        if clear:
            self.data = {}
        self.lock.release()
        return data
        
    def get_data_count(self) -> int:
        self.lock.acquire()
        count = self.data_count
        self.lock.release()
        return count

    def reset_data(self):
        self.lock.acquire()
        data = self.data
        self.data = {}
        self.lock.release()
        return data
        
    def reset_counter(self):
        self.lock.acquire()
        self.data_count = 0
        self.lock.release()
        
    def increment_counter(self) -> int:
        self.lock.acquire()
        self.data_count += 1
        count = self.data_count
        self.lock.release()
        return count
        
    def get_pi_temp(self, celsius : bool = False) -> float:
        try:
            sensor_temp = machine.ADC(4)
            conversion_factor = 3.3 / (65535)
            
            reading = sensor_temp.read_u16() * conversion_factor 
            celsius_degrees = 27 - (reading - 0.706)/0.001721
            fahrenheit_degrees = celsius_degrees * 9 / 5 + 32
            #print(celsius_degrees,'C', fahrenheit_degrees,'F')
            if celsius:
                return(celsius_degrees)
            else:    
                return(fahrenheit_degrees)    
        except Exception as e:
            print("Error getting temp\n%s" % e)
            return 0.0



