import socket
import logging
import threading
import time

from pyUDP import UDP

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("UDPTest")

def udp_client():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    while True:
        msg, addr = server_socket.recvfrom(1024)
        server_socket.sendto(msg, addr)

def test_udp():
    """Test sending data by checking if it is added to the TX queue."""

    server_thread = threading.Thread(target=udp_client, daemon=True)
    server_thread.start()
    time.sleep(1)

    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    packet = (b"Test Message", ("127.0.0.1", 12000))
    udp_obj.sendto(packet)

    time.sleep(1)

    # Check if the packet is in the RX queue
    rx_data = next(udp_obj.recv())
    server_thread.join()
    server_thread.stop()
    print(f"{rx_data = }")
    print("Recv test passed!")
    udp_obj.stop()

def test_stop_start():
    """Test stopping and restarting the UDP communication."""
    logger = logging.getLogger("UDPTest")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    # Stop communication
    udp_obj.stop()

    # Restart communication
    udp_obj.start()
    print("Stop/Start test passed!")
    udp_obj.stop()

def test_socket_close():
    """Test if the socket closes correctly on exit."""
    logger = logging.getLogger("UDPTest")
    udp_obj = UDP(logger=logger, local_address=("127.0.0.1", 12000))
    udp_obj.start()

    try:
        udp_obj._socket.sendto(b"Test", ("127.0.0.1", 12000))
    except OSError:
        print("Socket close test passed!")
        udp_obj.stop()
        return

    udp_obj.stop()
    raise AssertionError("Socket did not close properly")


if __name__ == "__main__":
    test_udp()
    test_stop_start()
    test_socket_close()

