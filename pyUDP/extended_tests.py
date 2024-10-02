import socket
import logging
import threading
import time
from queue import Queue
from random import randint, randbytes

from pyUDP import UDP

NUM_THREADS = 10
NUM_PACKETS = 1000
PACKETS = [randbytes(1024) for _ in range(NUM_PACKETS)]

logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
logger = logging.getLogger("UDPTest")

def stress_test_send(udp_obj, thread_id):
    """Function for sending data from multiple threads."""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM | socket.SOCK_NONBLOCK)
    global logger
    for count, pkt in enumerate(PACKETS):
        client_socket.sendto(pkt, ("127.0.0.1", 12000))
        logger.debug(f"Thread {thread_id} sent data packet n.{count}")
        time.sleep(randint(0, 10) / 10000)
    logger.info(f"Thread {thread_id} DONE")

def stress_test_recv(udp_obj, thread_id):
    """Function for receiving data in multiple threads."""
    global logger
    count = 0
    while True:
        try:
            data, sender = next(udp_obj.recv())
            if data:
                logger.debug(f"Thread {thread_id} received data packet n.{count}")
                logger.debug(f"Data complience {any(True for x in PACKETS if x == data)}")
                count += 1
            if count == NUM_PACKETS:
                logger.info(f"Thread {thread_id} DONE")
                break
        except StopIteration:
            pass  # No more data to receive, continue

def stress_test_multithreaded():
    """Stress test for multithreaded sending of data."""
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    # Create and start multiple sender threads
    send_threads = []
    for i in range(NUM_THREADS):
        thread = threading.Thread(target=stress_test_send, args=(udp_obj, i))
        send_threads.append(thread)
        thread.start()

    recv_thread = threading.Thread(target=stress_test_recv, args=(udp_obj, i))
    recv_thread.start()

    # Wait for all threads to finish
    for thread in send_threads:
        thread.join()

    recv_thread.join()

    udp_obj.stop()
    logger.info("Multithreaded sending stress test passed!")


if __name__ == "__main__":
    # Run the stress tests
    stress_test_multithreaded()

