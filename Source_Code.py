import socket
import time
import math

# Use the exact port you exposed in your QEMU command script
HOST = "127.0.0.1"
PORT = 5555  

# Starting Coordinates (Example: Central Park, NY)
BASE_LAT = 40.7851
BASE_LON = -73.9683
RADIUS = 0.005  
SPEED_FACTOR = 0.05  
angle = 0.0

def send_android_cmd(sock, command):
    """Sends a raw shell command directly over the QEMU network pipe."""
    try:
        sock.sendall(f"{command}\n".encode('utf-8'))
        # Clear the buffer response
        sock.recv(4096)
    except Exception:
        pass

print(f"Connecting to Android VM network port {PORT}...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    s.connect((HOST, PORT))
    print("[CONNECTED] Injection pipe is open. Google Maps will now update.")
    
    # Initialize the network shell connection
    s.sendall(b"CNXN\x00\x00\x00\x01\x00\x10\x00\x00\x00\x00\x00\x00") 
    time.sleep(0.5)

    while True:
        # Calculate moving coordinates loop
        lat = BASE_LAT + (RADIUS * math.sin(angle))
        lon = BASE_LON + (RADIUS * math.cos(angle))
        angle += SPEED_FACTOR

        # Force Android's internal location service to update immediately
        # This completely bypasses mock location permissions and hardware serial drivers
        cmd = f"cmd location set-location-update-provider gps {lat:.6f} {lon:.6f} 5.0"
        send_android_cmd(s, cmd)
        
        print(f"Injected into Google Maps -> Lat: {lat:.5f}, Lon: {lon:.5f}", end="\r")
        time.sleep(1.0)  # Update frequency (1Hz)

except KeyboardInterrupt:
    print("\nInjection stopped.")
except ConnectionRefusedError:
    print(f"\n[ERROR] Could not connect to QEMU on port {PORT}.")
    print("Make sure your QEMU VM is fully booted up and running first!")
finally:
    s.close()