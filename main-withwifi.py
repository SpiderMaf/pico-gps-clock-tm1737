# Conversion of Jeff Geerlings pico-time minirack code by SpiderMaf
# This is largely the same code but converted to use a tm1637 
# display rather than the adafrout one Jeff used.
#
# NEW version that uses WIFI time to begin with before locking onto GPS time
# Requires PiPico with Wifi.  Tested on Pi Pico W 2.
#
# requires wifi.txt file on root of pico with your wifi creds in.
#
# Requires tm1737.py library by Mike Causer
# https://github.com/mcauser/micropython-tm1637
#
# Jeff Geerling’s repository: 
# https://github.com/geerlingguy/time-pi/tree/master/pico-clock-mini-rack
#
# Jeff's original video on  @Level2Jeff  
# https://www.youtube.com/watch?v=E5qA4fgdS28
#
# Original Port details on Spidermaf video at:
# https://www.youtube.com/watch?v=K0nEwtgqVjg
# 
# Video about this code at:
# https://www.youtube.com/watch?v=hncMJelDq1k
#
#
# Original code below commented out

#



from machine import UART, Pin, I2C
#from ht16k33segment import HT16K33Segment
import tm1637
from micropyGPS import MicropyGPS
import time
import network
import ntptime
from machine import RTC

# 1. SETUP DISPLAY
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
#display = HT16K33Segment(i2c)
display = tm1637.TM1637(clk=Pin(5), dio=Pin(4))

#display.set_brightness(15)

# 2. SETUP GPS (UART0: TX=GP0, RX=GP1)
gps_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
my_gps = MicropyGPS(location_formatting='dd')

# 3. TIMEZONE & STATE TRACKING
STD_OFFSET = 0
had_fix = False  # Tracks previous state to prevent console spam

def get_local_time(gps_obj):
    h, m, s = gps_obj.timestamp
    return (h + STD_OFFSET) % 24, m, s

def show_dashes():
    #for i in range(4):
    #    display.set_glyph(0x40, i)
    display.show('----')
    
    #display.set_colon(False)
    #display.draw()
    
    
def get_signed_lat_lon(gps_obj):
    """
    With location_formatting='dd':
      gps_obj.latitude  -> [decimal_degrees, 'N'/'S']
      gps_obj.longitude -> [decimal_degrees, 'E'/'W']
    """
    lat_val, lat_hemi = gps_obj.latitude
    lon_val, lon_hemi = gps_obj.longitude

    latitude = -lat_val if lat_hemi == 'S' else lat_val
    longitude = -lon_val if lon_hemi == 'W' else lon_val

    return latitude, longitude


def print_fix_location(gps_obj):
    lat, lon = get_signed_lat_lon(gps_obj)
    # Print both signed decimal degrees + hemisphere for sanity
    print("GPS Fix Location:")
    print("  Latitude :", lat, gps_obj.latitude[1])
    print("  Longitude:", lon, gps_obj.longitude[1])
    
    
# ==========================
# READ WIFI CREDENTIALS
# ==========================

def read_wifi_credentials(filename="wifi.txt"):
    ssid = None
    password = None
    
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ssid="):
                    ssid = line.split("=", 1)[1]
                elif line.startswith("password="):
                    password = line.split("=", 1)[1]
    except OSError:
        print("Could not read wifi.txt file")
    
    return ssid, password

show_dashes()

SSID, PASSWORD = read_wifi_credentials()

if SSID is None or PASSWORD is None:
    raise RuntimeError("WiFi credentials not found in wifi.txt")

# ==========================
# WIFI CONNECTION
# ==========================

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

print("Connecting to WiFi...")

timeout = 15
while not wlan.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1

if not wlan.isconnected():
    raise RuntimeError("WiFi connection failed")

print("Connected!")
print("IP Address:", wlan.ifconfig()[0])

# ==========================
# NTP TIME SYNC
# ==========================

ntptime.host = "pool.ntp.org"
ntptime.settime()  # Sets RTC to UTC

print("Time synchronised with NTP")    










# --- STARTUP: WAIT FOR FIRST 3D FIX ---
print("System Starting... Waiting for initial 3D GPS fix.")
while True:
    if gps_uart.any():
        raw_data = gps_uart.read()
        for b in raw_data:
            try: my_gps.update(chr(b))
            except: continue

    if my_gps.fix_type == 3:
        print("Initial 3D Fix Acquired!")
        print_fix_location(my_gps)   # <-- NEW: print lat/lon once on first fix
        had_fix = True
        break

    # ==========================
    # APPLY UTC OFFSET
    # ==========================

    rtc = RTC()
    current_time = rtc.datetime()

    year, month, day, weekday, hour, minute, second, subsecond = current_time

    hour = hour + STD_OFFSET

    # Handle rollover
    if hour >= 24:
        hour -= 24
    elif hour < 0:
        hour += 24

    # ==========================
    # STORE TIME IN VARIABLES
    # ==========================

    hours = int(hour)
    minutes = int(minute)
    seconds = int(second)
    
    display.numbers(hours, minutes,int(seconds) % 2 == 0)
    
    time.sleep(0.1)

# --- MAIN LOOP ---
while True:
    if gps_uart.any():
        raw_data = gps_uart.read()
        for b in raw_data:
            try: my_gps.update(chr(b))
            except: continue

    # Check for State Changes in 3D Fix
    if my_gps.fix_type < 3 and had_fix:
        print("ALERT: 3D Fix Lost! Time may drift.")
        had_fix = False
    elif my_gps.fix_type == 3 and not had_fix:
        print("SUCCESS: 3D Fix Regained.")
        print_fix_location(my_gps)   # <-- NEW: print lat/lon once on first fix
        had_fix = True

    hours, minutes, seconds = get_local_time(my_gps)

    #display.set_number(hours // 10, 0)
    #display.set_number(hours % 10, 1)
    #display.set_number(minutes // 10, 2)
    #display.set_number(minutes % 10, 3)
    #display.numbers(hours, minutes)
    

    # Colon Logic: Flash if 3D Fix is active, Solid if Lost
    if had_fix:
        display.numbers(hours, minutes,True)
        #display.set_colon(int(seconds) % 2 == 0)
    else:
        display.numbers(hours, minutes,int(seconds) % 2 == 0)

    #display.draw()
    time.sleep(0.1)

