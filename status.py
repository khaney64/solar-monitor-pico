import time
import _thread
from influxdb_api_client import InfluxApiClient
from secrets import influxdb as influxdb_secrets
from machine import ADC, mem32, Pin

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
        #return 0.0
        try:
            self.lock.acquire()
            #print('open adc(4)')
            sensor_temp = ADC(4)
            conversion_factor = 3.3 / (1 << 16)
            
            #print('read temp')
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
        finally:
            self.lock.release()

    def setPad(self, gpio, value):
        mem32[0x4001c000 | (4+ (4 * gpio))] = value
        
    def getPad(self, gpio):
        return mem32[0x4001c000 | (4+ (4 * gpio))]

    # AA 1.35 to 1.5 volts (x3 = 4.05 to 4.5)
    # 3.75v Li 3.0 to 4.2
    def get_battery_voltage(self, min : float, max : float, samples : int = 3, adc_channel : int = 3) -> tuple[float, float]:
        #return 5.0, 100.0
        self.lock.acquire()
    
        now = time.localtime()
        print(f'{now[3]}:{now[4]}:{now[5]} - get vsys on {adc_channel} ')
        oldpad29 = None
        if adc_channel == 3:
            print('getPad(29)')
            oldpad29 = self.getPad(29)
            print(f'vsys setpad {oldpad29}')
            self.setPad(29,128)  #no pulls, no output, no input
            print('done setpad')
        try:
            vsys = ADC(adc_channel)
            gnd = ADC(1)
            conversion_factor = 3 * 3.3 / (1 << 16)
            
            voltage = 0.0
            ground = 0.0
            for s in range(samples):
                voltage += vsys.read_u16()
                ground += gnd.read_u16()
                print(f'vsys sample {s} vsys = {voltage/(s+1)}, gnd = {ground/(s+1)}')
            
            if adc_channel == 3:
                print('vsys restore pad')
                self.setPad(29,oldpad29)
            voltage = voltage / samples
            ground = ground / samples
            voltage = (voltage - ground) * conversion_factor
            percentage = 100 * ((voltage - min) / (max - min))
            if percentage > 100:
                percentage = 100.00
            return voltage, percentage 
        except Exception as e:
            print("Error getting voltage\n%s" % e)
            return 0.0, 0.0
        finally:
            if adc_channel == 3 and self.getPad(29) != oldpad29:
                print(f'vsys finally restore pad {oldpad29} from {self.getPad(29)}')
                self.setPad(29,oldpad29)
                print(f'vsys finally pad 29 now {self.getPad(29)}')
            self.lock.release()
    
    # Because I've been having problems on the pico-w getting vsys using ADC3, with various implementations, it will 
    # eventually hang for reasons unknown, likely due to conflict with the network chip.
    # I have added a voltage divider to the hardware from vsys to ground, 20k and 10k into ADC2, and ground is tied to ADC1 so 
    # I can get a more accurate vsys reading and hopefully not run into the hanging problem found on ADC3 which shares 
    # hardware with the wifi chip.
    # Ideally the divider would be vsys / 3, but resistors aren't exactly high quality, so not exactly what I want, so 
    # multipler is 3.7509 rather than 3.
    #
    # AA 1.35 to 1.5 volts (x3 = 4.05 to 4.5)
    # 3.75v Li 3.0 to 4.2
    def get_vsys_adc2(self, min : float, max : float, diode_drop : int = .2, samples : int = 3) -> tuple[float, float]:
        self.lock.acquire()
        try:
            vsys = ADC(2)
            gnd = ADC(1)
            # divider isn't quite 1/3, more like 4/15 or .2666 (so multiply by 3.7509)
            conversion_factor = 3.7509 * 3.3 / (1 << 16)
            raw = vsys.read_u16()
            ground = gnd.read_u16()
            vdivider = (raw - ground) * 3.3 / (1 << 16)
            vdivider += diode_drop
            voltage = (raw - ground) * conversion_factor
            voltage += diode_drop
            #print(f'adc2 - raw vsys = {raw}, raw around = {ground}, factor = {conversion_factor}, voltage = {voltage}, divider = {vdivider}')
            percentage = 100 * ((voltage - min) / (max - min))
            if percentage > 100:
                percentage = 100.00
            return voltage, percentage 
        except Exception as e:
            return 0.0
        finally:
            self.lock.release()

    def status_blink(self, count : int = 1, toggle_delay : float = .2, end_delay : float = 2):
        self.lock.acquire()
        led = Pin("LED", Pin.OUT)
        
        for repeat in range(count):
            led.on()
            time.sleep(toggle_delay)
            led.off()
            if repeat < count:
                time.sleep(toggle_delay)
        time.sleep(end_delay)
        self.lock.release()
        return
