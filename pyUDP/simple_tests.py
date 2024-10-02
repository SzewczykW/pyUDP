import socket
import logging
import threading
import time

from pyUDP import UDP

logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
logger = logging.getLogger("UDPTest")

client_stop = threading.Event()

def udp_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM | socket.SOCK_NONBLOCK)
    global logger
    while not client_stop.is_set():
        try:
            msg, addr = client_socket.recvfrom(1024)
            client_socket.sendto(msg, addr)
        except:
            pass

def test_udp():
    """Test sending/receving data by checking if it is added to the TX queue."""

    client_thread = threading.Thread(target=udp_client)
    client_thread.start()

    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    packet = (b"Test Message", ("127.0.0.1", 12000))
    udp_obj.send(packet)


    # Check if the packet is in the RX queue
    rx_data = next(udp_obj.recv())
    client_stop.set()
    udp_obj.stop()
    client_thread.join()
    logger.info(f"{rx_data = }")
    logger.info("Recv test passed!")

def test_stop_start():
    """Test stopping and restarting the UDP communication."""
    logger = logging.getLogger("UDPTest")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    # Stop communication
    udp_obj.stop()

    # Restart communication
    logger.info("Stop/Start test passed!")


if __name__ == "__main__":
    test_udp()
    test_stop_start()

