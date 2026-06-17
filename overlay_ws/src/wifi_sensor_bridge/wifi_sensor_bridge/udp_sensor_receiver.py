#!/usr/bin/env python3
import socket
import threading

import rclpy
from rclpy.node import Node

from std_msgs.msg import String

class UdpSensorReceiver(Node):
    def __init__(self) -> None:
        super().__init__("udp_sensor_receiver")

        # Declare parameters for UDP Port and IP
        self.declare_parameter("bind_ip", "192.168.178.176")
        self.declare_parameter("port", 5000)
        self.declare_parameter("max_datagram_size", 2048)

        self.declare_parameter("imu_topic", "/wifi/imu")
        self.declare_parameter("enc_topic", "/wifi/enc")
        self.declare_parameter("raw_topic", "/wifi/raw")

        self.bind_ip: str = self.get_parameter("bind_ip").get_parameter_value().string_value
        self.port: int = self.get_parameter("port").get_parameter_value().integer_value
        self.imu_topic: str = self.get_parameter("imu_topic").get_parameter_value().string_value
        self.enc_topic: str = self.get_parameter("enc_topic").get_parameter_value().string_value
        self.raw_topic: str = self.get_parameter("raw_topic").get_parameter_value().string_value
        self.max_datagram_size: int = self.get_parameter("max_datagram_size").get_parameter_value().integer_value

        # Setup publishers for sensor data
        self.raw_pub = self.create_publisher(String, self.raw_topic, 10)
        self.imu_pub = self.create_publisher(String, self.imu_topic, 10)
        self.enc_pub = self.create_publisher(String, self.enc_topic, 10)

        # Create the UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.bind_ip, self.port))
        self.sock.settimeout(1.0)

        # Start the receive loop
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self.recv_loop, daemon=True)
        self._thread.start()

        # Logging
        self.get_logger().info(f"Listening UDP on {self.bind_ip}:{self.port}")
        self.get_logger().info(f"Publishing IMU data on: {self.imu_topic}")
        self.get_logger().info(f"Publishing Encoder data on: {self.enc_topic}")

    def recv_loop(self) -> None:
        while rclpy.ok() and not self._stop_event.is_set():
            try:
                # Receive the data
                data, add = self.sock.recvfrom(self.max_datagram_size)
                payload = data.decode("utf-8", errors="replace").strip()

                # Publish raw incoming data for debug
                raw_msg = String()
                raw_msg.data = payload
                self.raw_pub.publish(raw_msg)

                # Split data into proper channels and publish on respective topics
                values = payload.split(',')
                rpy_msg = String()
                rpy_str = values[0] + "," + values[1] + "," + values[2]
                rpy_msg.data = rpy_str
                self.imu_pub.publish(rpy_msg)

                enc_msg = String()
                enc_str = values[3] + "," + values[4] + "," + values[5] + "," + values[6]
                enc_msg.data = enc_str
                self.enc_pub.publish(enc_msg)

            except socket.timeout:
                continue
            except Exception as e:
                self.get_logger().error(f"Socket error: {e}")
                continue


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UdpSensorReceiver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()