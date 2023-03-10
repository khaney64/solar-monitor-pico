from wifi import Wifi
from secrets import wifi as wifi_secrets
from influxdb_api_client import Point
from server import Request
from machine import Timer, I2C, Pin
from time import sleep, localtime
from ntptime import settime
from _thread import allocate_lock
from sys import print_exception
import gc
from status import Status
from lib.ina219 import INA219
import logging

lock = allocate_lock()

def handle_request(request : Request, status : Status) -> str:
    #print('web request')
    #print(request.verb, request.command)
    global timer
    global ina
    
    command = request.command.lower()
    if command == "/start":
        if status.get_state() == 'waiting':
            status.update_state('monitoring')
            status.reset_counter()
            ina.wake()
            location, delay = status.get_config()
            timer.init(period=delay*1000, mode=Timer.PERIODIC, callback=fetch_and_write_data)
            #start_new_thread(monitor_thread,(status,))
            print(f'---- Start monitoring request, using location {status.location}, delay {status.delay}')
            status_blink(2)

    elif command == "/stop":
        if status.get_state() == 'monitoring':
            status.update_state('waiting')
            timer.deinit()
            ina.sleep()
            print(f'---- Stop monitoring request, logged {status.get_data_count()} data points')
            status_blink(3)
        
    elif command == "/config":
        if status.get_state() != 'waiting':
            print('---- config ignored, not waiting')
            return ""
        location, delay = status.get_config()
        changedto = ''
        if 'location' in request.parameters:
            location = request.parameters['location']
        if 'delay' in request.parameters:
            newdelay = request.parameters['delay']
            if int(newdelay) >= 2 and newdelay != delay:
                delay = int(newdelay)
                changedto = 'changed to '
        status.update_config(location, delay)
        print(f'---- Configure request, location {status.location}, delay {changedto}{status.delay}')
    else:
        data_str = ''
        if status.get_state == 'monitoring':
            data_str = f', {status.get_data_count()} data points captured'
        print(f'---- Status request, {status.state} location {status.location}, delay {status.delay}{data_str}')
    return ""

def webserver_start(status : Status):
    from server import WebServer
    webserver = WebServer(status)

    try:
        webserver.listen(handle_request)
        print('-- webserver listen stopped')
        sleep(10)
    except Exception as e:
        print_exception(e)
    except KeyboardInterrupt as ke:
        print_exception(ke)

    print('-- webserver shutdown')
    webserver.shutdown()
    
def fetch_and_write_data(timer : Timer):
    global status
    global timer_fired
    global freemem
    global ina
    
    if timer_fired:
        print('** timer fired, already busy')
        status_blink(10,.1,.5)
        return

    timer_fired = True

    points = []
    try:
        if freemem != gc.mem_free():
            freemem = gc.mem_free()
            if (freemem < 50000):
                print(f'Memory is below 50K! : {freemem}')
        gc.collect()
        #print(f'** gc collect end {freemem}')

        if status.get_state() != 'monitoring':
            print(f'** timer fired - not monitoring now')
            timer_fired = False
            return
        
        location, delay = status.get_config()
        now = localtime()

        print(f'** {now[3]}:{now[4]}:{now[5]} : timer fired, monitoring location {location}, delay {delay}')
        
        # fetch from ina219 here
        #print('getting ina #s')
        diode_drop = .8 # need to put a .2 diode in here
        voltage = ina.voltage() + diode_drop # volts
        current = ina.current() / 1000 # reading is amps, convert to milliamps
        power = ina.power() / 1000 # reading is watts, convert to milliwatts
        #print('getting temp')
        temperature = status.get_pi_temp()
        #print(ina.voltage(),ina.current(),ina.power())
        #print(voltage,current,power,temperature)

        #print('getting vsys')
        #vsys, percentage = status.get_battery_voltage(3.0, 4.2, adc_channel=3)
        vsys, percentage = status.get_vsys_adc2(3.0,4.2)
        #print(vsys,percentage)

        points.append(Point("voltage",{('location',location),('measurement','voltage'),('units','Volt')},voltage))
        points.append(Point("current",{('location',location),('measurement','current'),('units','Amp')},current))
        points.append(Point("power",{('location',location),('measurement','power'),('units','Watt')},power))
        points.append(Point("temperature",{('location',location),('measurement','temperature'),('units','Fahrenheit')},temperature))
        points.append(Point("vsys",{('location',location),('measurement','vsys'),('units','Volt')},vsys))
        points.append(Point("battery",{('location',location),('measurement','battery'),('units','Percent')},percentage))
        points.append(Point("freemem",{('location',location),('measurement','freemem'),('units','Byte')},freemem))

        #print(f'influx write start {status.get_data_count()}')
        if status.influxdbclient.write_with_retry(points, tries=1, delay=1):
            count = status.increment_counter()
            if count % 100 == 0:
                print(f'++ Recorded {count} records')
        #print(f'influx write end {status.get_data_count()}')
        status.status_blink(1)

    except Exception as e:
        print_exception(e)
    finally:
        timer_fired = False
        points = None
    return

def status_blink(count : int = 1, toggle_delay : float = .2, end_delay : float = 2):
    global led_pin
    
    for repeat in range(count):
        led_pin.on()
        sleep(toggle_delay)
        led_pin.off()
        if repeat < count:
            sleep(toggle_delay)
    sleep(end_delay)
    return

if __name__ == "__main__":
    """
    Led blink sequence on startup
    1 - starting
    2 - wifi started
    3 - npt time set (or attempted)
    4 - 
    """
    print('monitor.py main')

    led_pin = Pin("LED", Pin.OUT)
    
    status_blink(1)

    ssid = wifi_secrets['ssid']
    password = wifi_secrets['password']

    wifi = Wifi(ssid,password)
    wifi.start()
    
    status_blink(2)

    try:
        settime()
        print("time set from npt to???%s" %str(localtime()))
    except Exception as e:
        print('nptime settimee() failed')
        print_exception(e)
    status_blink(3)

    threadrunning = False
    #webthread = _thread.start_new_thread(webserver_thread, ())
    
    # we're in one of two states in the main loop.
    # waiting - wait for web requests
    #   configure - set location and delay values
    #   status - return status info (waiting or monitoring, configuration)
    #   start - start monitoring (switch to monitoring state)
    # monitoring - wait for web requests
    #   status - return status info (waiting or monitoring, configuration, latest readings)
    #   stop - stop monitoring (switch to waiting state)
    
    status = Status(lock)
    location, delay = status.get_config()
    
    timer_fired = False
    timer = Timer()

    sda = Pin(10)
    scl = Pin(11)
    i2c = I2C(1, sda=sda, scl=scl, freq=400000)

    I2C_INTERFACE_NO = 1
    SHUNT_OHMS = 0.1  # Check value of shunt used with your INA219

    ina = INA219(SHUNT_OHMS, I2C(I2C_INTERFACE_NO), log_level=logging.INFO)
    ina.configure(voltage_range=INA219.RANGE_16V, gain=INA219.GAIN_1_40MV )

    # scan i2c - should find
    # ina219 at x40
    # ssd1306 at x3C (todo)
    devices = i2c.scan()
    for d in devices:
        print(f'found {hex(d)}')
    if len(devices) < 1:
        print('not all i2c devices found')
        status_blink(4, 1)
    else:
        status_blink(4)

    ina.sleep()

    freemem = 0
    
    while True:
        status_blink(5)
        print('-- starting webserver')
        webserver_start(status)
        # webserver should run forever unless it crashes.
        # we do want to restart it, but may need to clean some things up (or start  might not work)
        print('-- stopping timer')
        timer.deinit()
        sleep(10)

    
