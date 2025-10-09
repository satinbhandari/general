import threading
import redis
import uvicorn
import os
import signal
import sys
import time

def redis_kill_listener(shutdown_callback, channel='kill_channel'):
    r = redis.Redis()
    p = r.pubsub()
    p.subscribe(channel)
    print(f"Listening for kill signal on {channel}...")
    for message in p.listen():
        if message['type'] == 'message' and message['data'] == b'kill':
            print("Kill signal received via Redis.")
            shutdown_callback()
            break

def shutdown_uvicorn():
    print("Shutting down Uvicorn server and exiting process.")
    # Method 1: Send SIGINT to self (simulate Ctrl+C)
    os.kill(os.getpid(), signal.SIGINT)
    # Method 2: If that doesn't work, force exit
    # os._exit(0)

def start_app_with_listener():
    # Start Redis kill listener in background
    listener_thread = threading.Thread(target=redis_kill_listener, args=(shutdown_uvicorn,))
    listener_thread.daemon = True
    listener_thread.start()

    # Start Uvicorn - replace "app:app" with your import path!
    uvicorn.run("app:app", host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start_app_with_listener()
