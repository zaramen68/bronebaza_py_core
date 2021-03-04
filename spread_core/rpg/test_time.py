import time

current_milli_time = lambda: int(round(time.time() * 1000))

while True:
    t=int(round(time.time() * 1000))
    print(current_milli_time())


