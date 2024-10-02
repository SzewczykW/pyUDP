import socket
import logging
import threading
import time
from queue import Queue

import pyUDP

NUM_THREADS = 10
NUM_PACKETS = 1000

def stress_test_send(udp_obj, packet, thread_id):
    """Function for sending data from multiple threads."""
    for i in range(NUM_PACKETS):
        udp_obj.sendto((f"Message {i} from Thread {thread_id}".encode(), ("127.0.0.1", 8059)))
        time.sleep(0.001)  # Slight delay to simulate real-world sending

def stress_test_recv(udp_obj, thread_id):
    """Function for receiving data in multiple threads."""
    for i in range(NUM_PACKETS):
        try:
            data = next(udp_obj.recv(1))
            if data:
                print(f"Thread {thread_id} received data: {data[0]}")
        except StopIteration:
            pass  # No more data to receive, continue

def stress_test_multithreaded_sending():
    """Stress test for multithreaded sending of data."""
    logger = logging.getLogger("UDPStressTestSend")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 8059))
    udp_obj.start()

    # Create and start multiple sender threads
    threads = []
    for i in range(NUM_THREADS):
        thread = threading.Thread(target=stress_test_send, args=(udp_obj, b"Test message", i))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    print("Multithreaded sending stress test passed!")

def stress_test_multithreaded_receiving():
    """Stress test for multithreaded receiving of data."""
    logger = logging.getLogger("UDPStressTestRecv")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 8060))
    udp_obj.start()

    # Create a client that will send data to the UDP server
    def send_packets():
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for i in range(NUM_PACKETS):
            client_socket.sendto(f"Packet {i}".encode(), ("127.0.0.1", 8060))
            time.sleep(0.001)  # Simulate slight delay

    client_thread = threading.Thread(target=send_packets)
    client_thread.start()

    # Create and start multiple receiver threads
    threads = []
    for i in range(NUM_THREADS):
        thread = threading.Thread(target=stress_test_recv, args=(udp_obj, i))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    client_thread.join()
    for thread in threads:
        thread.join()

    print("Multithreaded receiving stress test passed!")

def high_volume_test():
    """High volume test for sending and receiving a large number of packets."""
    logger = logging.getLogger("UDPHighVolumeTest")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 8061))
    udp_obj.start()

    # Function to send many packets in rapid succession
    def high_volume_sender():
        for i in range(5000):  # Sending 5000 packets
            udp_obj.sendto((f"High volume message {i}".encode(), ("127.0.0.1", 8061)))
            time.sleep(0.0001)  # Very slight delay to simulate real-world usage

    # Simulate a UDP client sending data
    def udp_client_send():
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for i in range(5000):
            client_socket.sendto(f"High volume packet {i}".encode(), ("127.0.0.1", 8061))
            time.sleep(0.0001)

    # Start the client sending thread
    client_thread = threading.Thread(target=udp_client_send)
    client_thread.start()

    # Start the high volume sender in UDP object
    sender_thread = threading.Thread(target=high_volume_sender)
    sender_thread.start()

    # Give time to process
    time.sleep(2)

    # Verify that packets were received
    received_count = 0
    for _ in range(5000):
        pkt = next(udp_obj.recv(1))
        if pkt:
            received_count += 1

    print(f"High volume test completed. Total packets received: {received_count}")

    client_thread.join()
    sender_thread.join()

    print("High volume stress test passed!")


if __name__ == "__main__":
    # Run the stress tests
    stress_test_multithreaded_sending()
    stress_test_multithreaded_receiving()
    high_volume_test()

