import logging
import socket
import threading

from time import time_ns
from queue import SimpleQueue, Queue, Empty, Full
from typing import Callable, Optional, Tuple, Union


__all__ = ["UDP", "UDPCommunicationIsStopped"]


class UDPCommunicationIsStopped(Exception):
    """
    Excepction raised when trying to execute `UDP.recv()` or `UDP.sendto` when
    `UDP.__stop` is set.
    """


class UDP:
    """
    Handles sending and receiving data asynchronously
    over bounded UDP socket using separate RX and TX threads.
    """

    def __init__(
        self,
        local_address: Tuple[str, int],
        rx_with_timestamps: bool = False,
        logger: Optional[logging.Logger] = None,
        socket_timeout: Optional[float] = None,
        socket_rx_buff_size: int = 750_000,
        rx_pkt_size: int = 1024,
    ):
        """
        Initializes the UDP socket and starts RX and TX threads.

        Parameters:
        * `logger` (Optional[logging.Logger]): Logger instance, creates one without
          filters if not provided.
        * `local_address` (Tuple[str, int]): Tuple containing the local IPv4 address
          and port for binding UDP server socket.
        * `rx_with_timestamps` (bool): set `True` if `UDP._RX` thread should add
          timestamps to received data.
        * `socket_timeout` (float): Timout in secends for socket operations.
        * `socket_rx_buff_size` (int): socket recv buffer size. If bigger than system
          wide rmem_size_max then the rmem_size_max is set.
        * `rx_pkt_size` (int): Maximum packet size to be received.
        """
        self.logger = logger or logging.getLogger(
            f"{self.__class__.__name__}-{local_address[0]}:{local_address[1]}"
        )
        if not logger:
            self.logger.setLevel(logging.ERROR)

        self.local_address = local_address

        self.rx_with_timestamps = rx_with_timestamps

        self.rx_pkt_size = rx_pkt_size

        self._socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM | socket.SOCK_NONBLOCK
        )

        self._socket.bind(local_address)

        if socket_timeout is not None:
            self._socket.settimeout(socket_timeout)

        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, socket_rx_buff_size)

        self.logger.info(
            f"UDP socket bound to {self.local_address} with timeout: {socket_timeout}"
        )

        self.__stop = threading.Event()

    def __exit__(self):
        """
        Stop the UDP communication and close the socket at exit.
        """
        self.logger.info("Stopping UDP connection...")
        self.set_stop()
        self._socket.close()
        self.logger.info("UDP socket closed")

    def is_stopped(self) -> bool:
        """
        Checks `self.__stop` flag.

        Returns:
        * `bool`: `True` if UDP communication is stopped else `False`.
        """
        return self.__stop.is_set()

    def stop(self) -> None:
        """
        Stop the communication by deleting RX and TX thread objects. Can be started over again by
        `self.set_start()`.
        """
        self.logger.info("Stopping UDP communication...")

        self.__stop.set()

        self.logger.debug("Waiting for RX thread to finish...")
        self._rx.join()  # Wait for the RX thread to finish
        self.logger.debug("RX thread finished")

        self.logger.debug("Waiting for TX thread to finish...")
        self._tx.join()  # Wait for the TX thread to finish
        self.logger.debug("TX thread finished")

        self._rx = None
        self._tx = None

        self.logger.info("Stopped UDP communication.")

    def start(self) -> None:
        """
        Start the UDP communication by creating RX and TX threads.
        """
        self.logger.info("Starting UDP communication...")
        self.__stop.clear()

        self._rx = UDP._RX(
            self.logger,
            self._socket,
            self.is_stopped,
            self.rx_with_timestamps,
            self.rx_pkt_size,
        )
        self._tx = UDP._TX(self.logger, self._socket, self.is_stopped)

        self._rx.start()
        self._tx.start()

        self.logger.info("UDP started communication.")

    def recv(
        self, block: bool = False, timeout: float = None
    ) -> Optional[Tuple[bytes, Optional[int]]]:
        """
        Receive data form RX queue.

        Parameters:
        * `block` (bool): blocking flag for `_RX._rx_queue.get`.
        * `timeout` (float): timeout value for `_RX._rx_queue.get`.

        Raises:
        * `UDPCommunicationIsStopped`: Exception when called and `self.__stop` is set.

        Returns:
        * (Optional[Tuple[bytes, Optional[int]]]): Return received packet poped from RX queue.
        """
        if self.is_stopped():
            raise UDPCommunicationIsStopped(
                "Cannot perform UDP action when threads are not running!"
            )

        return self._rx.get_pkt(block, timeout)

    def send(
        self,
        pkt: Tuple[Union[bytes, bytearray], Tuple[str, int]],
        block: bool = True,
        timeout: float = None,
    ) -> None:
        """
        Send data by putting it in TX queue.

        Parameters:
        * `pkt` (Tuple[Union[bytes, bytearray], Tuple[str, int]]): Tuple containing message to be
          sent(can be empty) and Tuple with IPv4 address(str) of receiver as
          first element and port(int) as second.
        * `block` (bool): blocking flag for `_TX._tx_queue.put`.
        * `timeout` (float): timeout value for `_RX._rx_queue.put`.

        Raises:
        * `UDPCommunicationIsStopped`: when called and `self.__stop` is set.
        * `ValueError`: if packet tuple is not properly structured.
        * `TypeError`: if address components have wrong types.
        """
        if not isinstance(pkt, tuple) or len(pkt) != 2:
            raise ValueError(
                "Packet must be a tuple of (data: Union[bytes, bytearray], address: Tuple[str, int])."
            )

        data, addr = pkt
        if not isinstance(addr, tuple) or len(addr) != 2:
            raise ValueError("Address must be a tuple of (host: str, port: int).")

        host, port = addr
        if not isinstance(host, str):
            raise TypeError(f"Host must be a string, got {type(host)}.")
        if not isinstance(port, int):
            raise TypeError(f"Port must be an integer, got {type(port)}.")

        if self.is_stopped():
            raise UDPCommunicationIsStopped(
                "Cannot perform UDP action when threads are not running!"
            )

        self._tx.send_pkt(pkt, block, timeout)

    class _RX(threading.Thread):
        """
        RX class thread responsible of receiving packets from UDP socket and putting it into RX queue.
        """

        def __init__(
            self,
            logger: logging.Logger,
            socket: socket.socket,
            stop: Callable[[], bool],
            with_timestamps: bool = False,
            pkt_size: int = 1024,
        ):
            """
            Initialize the RX thread.

            Parameters:
            * `logger` (logging.Logger): Logger instance passed by primary UDP class object.
            * `socket` (socket.socket): Python socket object instance passed by primary UDP class object.
            * `stop` (Callable[[], bool]): internal `UDP` method for thread communication when to stop.
            * `with_timestamps` (bool): flag for adding timestamps to received data from socket.
            * `pkt_size` (int): Maximum size of packet to be received.
            """
            super().__init__()
            self.__stop = stop

            self._socket = socket

            self.logger = logger

            self.pkt_size = pkt_size
            self.with_timestamps = with_timestamps
            self._rx_queue = SimpleQueue()

        def run(self) -> None:
            """
            Main loop of RX thread. Receives packets and puts them into RX queue.
            """
            self.logger.debug("RX thread started")
            while not self.__stop():
                try:
                    response = self._socket.recv(self.pkt_size)
                    self._rx_queue.put_nowait(
                        (
                            response,
                            (time_ns() if self.with_timestamps else None),
                        )
                    )
                except OSError as e:
                    self.logger.debug(
                        "Socket probably timed out at receiving data."
                    )
                    self.logger.debug(f"SOCKET_ERROR: {e}")
                    continue
                except Full:
                    self.logger.error("RX queue is full!")
                    continue
            self.logger.debug("Waiting for user to receive all packages from RX queue.")
            while not self._rx_queue.empty():
                pass
            self.logger.debug("RX thread leaving")

        def get_pkt(
            self, block: bool = False, timeout: float = None
        ) -> Optional[Tuple[bytes, Optional[int]]]:
            """
            Pop message from RX queue.

            Parameters:
            * `block` (bool): blocking flag for `UDP._RX._rx_queue.get`.
            * `timeout` (float): timeout value for `UDP._RX._rx_queue.get`.

            Returns:
            * (Optional[Tuple[bytes, Optional[int]]]): Data received or None if queue is empty.
            """
            try:
                data = self._rx_queue.get(block, timeout)
                return data
            except Empty:
                self.logger.warning("RX queue is empty, nothing to return")
                return None

    class _TX(threading.Thread):
        """
        TX class thread responsible of sending packets over UDP socket from TX queue.
        """

        def __init__(
            self,
            logger: logging.Logger,
            socket: socket.socket,
            stop: Callable[[], bool],
        ):
            """
            Initialize the TX thread.

            Parameters:
            * `logger`(logging.Logger): Logger instance passed by primary UDP class object.
            * `socket`(socket.socket): Python socket object instance passed by primary UDP class object.
            * `stop` (Callable[[], bool]): internal `UDP` method for thread communication when to stop.
            """
            super().__init__()
            self.__stop = stop

            self._socket = socket

            self.logger = logger

            self._tx_queue = Queue()

        def run(self) -> None:
            """
            Main loop of TX thread. Sends packets get from TX queue over UDP socket.
            """
            self.logger.debug("TX thread started")
            while not self.__stop():
                try:
                    data, remote_address = self._tx_queue.get_nowait()
                    ret = self._socket.sendto(data, remote_address)
                    if ret != len(data):
                        self.logger.warning(
                            f"Could not send message in full. Message sent: {data[:ret]}"
                        )
                    self.logger.debug(f"Sent message to {remote_address}")
                except OSError as e:
                    self.logger.error("Socket failed to send data.")
                    self.logger.error(f"SOCKET_ERROR: {e}")
                    continue
                except Empty:
                    self.logger.info("Nothing to send, continuing.")
                    continue
                except ValueError:
                    self.logger.critical(
                        f"Invalid structure in TX queue. Must be (data, remote_address). Dumping last added element"
                    )
                    _ = self._tx_queue.get_nowait()  # Dump invalid element
                    continue
            self.logger.debug("TX thread leaving")

        def send_pkt(
            self,
            tx_pkt: Tuple[Union[bytes, bytearray], Tuple[str, int]],
            block: bool = True,
            timeout: float = None,
        ) -> None:
            """
            Put packet into TX queue.

            Parameters:
            * `tx_pkt` (Tuple[Union[bytes, bytearray], Tuple[str, int]]): Tuple containing message to be
              sent(can be empty) and Tuple with IPv4 address(str) of receiver as
              first element and port(int) as second.
            * `block` (bool): blocking flag for `UDP._TX._tx_queue.put`.
            * `timeout` (float): timeout value for `UDP._TX._tx_queue.put`.
            """
            try:
                self._tx_queue.put(tx_pkt, block, timeout)
            except Full:
                self.logger.critical("TX queue is full!")
