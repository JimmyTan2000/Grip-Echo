import machine
import neopixel
import time

# --- Configuration ---
NUM_LEDS = 8

# -- THRESHOLDS --
# MIN_THRESHOLD is now dynamically calculated during startup
MIN_THRESHOLD = 0
MAX_THRESHOLD = 22000  # Anything above this is 100% (Full power)

# -- SERVO CALIBRATION --
# 50Hz means a 20ms period. 65535 = 20ms.
# MG996R typically uses ~0.5ms (1638) for 0 degrees, and ~2.5ms (8192) for 180 degrees.
# Adjust these slightly if your servo hits its physical limits and "buzzes".
SERVO_MIN = 1638
SERVO_MAX = 8192

# --- Hardware Setup ---
# LEDs on GP14
# Green
np = neopixel.NeoPixel(machine.Pin(14), NUM_LEDS)

# Vibration Motor on GP15 (1000Hz for smooth DC speed control)
# yellow
motor = machine.PWM(machine.Pin(15))
motor.freq(1000)

# MG996R Servo on GP0 (50Hz for standard servo signal)
# Orange
servo = machine.PWM(machine.Pin(0))
servo.freq(50) 

# 3x Joy-IT Sensors on ADC0, ADC1, ADC2 (GP26, GP27, GP28)
sensor1 = machine.ADC(machine.Pin(26))
sensor2 = machine.ADC(machine.Pin(27))
sensor3 = machine.ADC(machine.Pin(28))


# --- Auto Calibration Routine ---
print("Calibrating sensors for 5 seconds... Please do not touch/flex.")

calib_start = time.ticks_ms()
max_resting_value = 0

# Sample the sensors for 5000 milliseconds (5 seconds)
while time.ticks_diff(time.ticks_ms(), calib_start) < 5000:
    v1 = sensor1.read_u16()
    v2 = sensor2.read_u16()
    v3 = sensor3.read_u16()
    
    # Find the highest spike of noise during the resting phase
    current_max = max(v1, v2, v3)
    if current_max > max_resting_value:
        max_resting_value = current_max
        
    time.sleep(0.01) # Small delay to prevent locking up the processor

# Set the min threshold to the highest resting noise found + a deadzone buffer of 500
MIN_THRESHOLD = max_resting_value + 500

# Failsafe just in case baseline reads unusually high
if MIN_THRESHOLD >= MAX_THRESHOLD:
    MIN_THRESHOLD = MAX_THRESHOLD - 1000

print(f"Calibration Complete! MIN_THRESHOLD set to: {MIN_THRESHOLD}")


# --- Success Indication ---
# Vibrate for ~2 seconds while simultaneously blinking green 3 times
motor.duty_u16(65535) # Turn motor on full

for _ in range(3):
    # All Green
    for i in range(NUM_LEDS):
        np[i] = (0, 255, 0)
    np.write()
    time.sleep(0.33)
    
    # All Off
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()
    time.sleep(0.33)
    # Note: 3 loops of (0.33s + 0.33s) equals ~1.98 seconds, which perfectly matches your 2-second motor requirement!

motor.duty_u16(0) # Turn motor off
print("System Ready!")


# --- Main Logic ---
def get_ratio(raw_val):
    """Converts a raw sensor reading to a 0.0 - 1.0 ratio based on thresholds."""
    if raw_val <= MIN_THRESHOLD:
        return 0.0
    elif raw_val >= MAX_THRESHOLD:
        return 1.0
    else:
        return (raw_val - MIN_THRESHOLD) / (MAX_THRESHOLD - MIN_THRESHOLD)

while True:
    # 1. Read the raw sensor values
    val1 = sensor1.read_u16()
    val2 = sensor2.read_u16()
    val3 = sensor3.read_u16()
    
    # 2. Convert each reading to a percentage (0.0 to 1.0)
    ratio1 = get_ratio(val1)
    ratio2 = get_ratio(val2)
    ratio3 = get_ratio(val3)
    
    # 3. Determine the overall output level using the AVERAGE of the 3 sensors
    active_ratio = (ratio1 + ratio2 + ratio3) / 3.0
    
    # Print the values and the calculated total power to the console
    print(f"S1: {val1} | S2: {val2} | S3: {val3} | Power: {int(active_ratio * 100)}%")
    
    # 4. Update Vibration Motor Intensity linearly
    motor.duty_u16(int(active_ratio * 65535))
    
    # 5. Update Servo Position (Map 0.0-1.0 ratio to Servo Min-Max Duty)
    servo_duty = int(SERVO_MIN + (active_ratio * (SERVO_MAX - SERVO_MIN)))
    servo.duty_u16(servo_duty)
    
    # 6. Calculate Color (Blend from Green to Red)
    red = int(active_ratio * 255)
    green = int((1.0 - active_ratio) * 255)
    blue = 0
    
    # 7. Calculate how many LEDs to light up (0 to 8)
    leds_to_light = int(active_ratio * NUM_LEDS)
    # Ensure it reaches the top LED if pushed hard enough
    if active_ratio >= 0.95:
        leds_to_light = 8
    
    # 8. Update the LED Strip
    for i in range(NUM_LEDS):
        if i < leds_to_light:
            np[i] = (red, green, blue)
        else:
            np[i] = (0, 0, 0) 
            
    np.write()
    
    # A slightly longer delay so the console prints are readable
    time.sleep(0.05)