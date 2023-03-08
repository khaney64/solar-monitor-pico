# Raspberry Pi Pico W / INA219 Solar Monitor
This is a modification of the Raspberry Pi solar monitor project, but adapted to use a Raspberry Pi Pico W microcontroller.
This gave me a chance to clean up the hardware into a smaller, cleaner package, as well as learn how to code the Pico with micropython.
Unfortunately a lot of the code from the original project could not be used, so had to be replaced (ina219 and display code modules), or written from scratch (influxdb client and webserver code written from scratch).
Since the pico doesn't have an OS, and I can't ssh in to start the program, it has a webserver interface with a simple list of commands:
- status - return status
- config - set the location and delay parameters
- start - start monitoring
- stop - stop monitoring

As with the original project, the data is captured and sent to influxdb, and graphed with grafana.
Because the pico uses so little power compared to the Pi zero in the other project, the battery pack I used for that one would shut down after 20 seconds, so I had to use a different batter pack.

Again as with the original, it uses the INA219 High Side DC Current Sensor on the I2C bus, and uses a different display this time, the smaller SSD1306, also on the I2C bus.

**hardware**:
- Raspberry Pi Pico W
- [ina219](https://www.adafruit.com/product/904)
- [Voltaic Systems 6V 2W solar panel](https://www.adafruit.com/product/5366)
- a few resistors disipate up to 2 Watts of power at peak, and a diode to prevent back flow of current through the solar panel.
- connectors/wires to connect to the I2C bus and power on the Pi's GPIO.

**configuration**:
secrets.py config file should contain the following information to define the wifi SSID and password, and connect to the influx db (see secrets-sample.py for example):

>wifi = {
>    'ssid' : '<ssid here>',
>    'password' : '<password here>',
>}
>
>influxdb = {
>    'url': '<influxdb url>',
>    'organization': '<organization>',
>    'bucket': '<bucket>',
>    'token': '<token>'
>}

**screenshots**:
Here is the assembled monitor:
![monitor](/screenshots/monitor-1.jpg)

Solar input side.  button currently not used, but will likely be used to toggle the display (todo):
![inside](/screenshots/monitor-2.jpg)

Power input side.  The device doesn't draw as much power as the original Pi Zero version, so the USB battery I was using kept shutting off.
I added a JST power connector, so it can be powered that way, or via the USB connector:
![inside](/screenshots/monitor-3.jpg)

Using the JST power connector with ![3.7v 2200 mAh LiPo battery](https://www.adafruit.com/product/1781#tutorials) :
![inside](/screenshots/monitor-4.jpg)

