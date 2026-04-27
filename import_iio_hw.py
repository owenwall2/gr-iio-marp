import iio_hw


remote_ip = "ip:192.168.178.2"

try:
    ctx = iio_hw.Context(remote_ip)
    print("Nices")

except Exception as e:
    print(f"Conection failed: {e}")