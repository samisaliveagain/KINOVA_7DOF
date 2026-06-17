import sys
import threading
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt5 import QtCore

class ControlGui(Node):
    def __init__(self):
        super().__init__('control_gui')

        #Sub to ui_data topic for getting updated values
        self.data_sub = self.create_subscription(String, '/servo_control/ui_data', self.data_receive, 10)
 
        #UI Variables
        self.control_labels = ["Translation", "Orientation", "Gripper"]
        self.ref_labels = ["base_link", "end_effector_link", "gripper"]
        self.run_labels = ["OFF", "ON"]
        self.r = 0.0
        self.p = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        
        self.run_mode = 0
        self.control_mode = 0
        self.homing_status = 0
        self.servo_service = 0
        self.gripper_pos = 0.0
        self.ir_sw = 1

        # Create the Qt window
        self.app = QApplication(sys.argv)
        self.window = QWidget()
        self.window.setWindowTitle("Kortex Gen3 Display GUI")
        self.outerlayout = QVBoxLayout()
        self.firstRowLayout = QHBoxLayout()
        self.secondRowLayout = QHBoxLayout()
        self.thirdRowLayout = QHBoxLayout()
        self.fourthRowLayout = QHBoxLayout()
        self.fifthRowLayout = QHBoxLayout()

        self.outerlayout.addLayout(self.firstRowLayout)
        self.outerlayout.addLayout(self.secondRowLayout)
        self.outerlayout.addLayout(self.thirdRowLayout)
        self.outerlayout.addLayout(self.fourthRowLayout)
        self.outerlayout.addLayout(self.fifthRowLayout)

        self.label1 = QLabel("IMU Roll: 0")
        self.label1.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label2 = QLabel("IMU Pitch: 0")
        self.label2.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label3 = QLabel("IMU Yaw: 0")
        self.label3.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.firstRowLayout.addWidget(self.label1)
        self.firstRowLayout.addWidget(self.label2)
        self.firstRowLayout.addWidget(self.label3)

        self.label4 = QLabel("VX: 0")
        self.label4.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label5 = QLabel("VY: 0")
        self.label5.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label6 = QLabel("VZ: 0")
        self.label6.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.secondRowLayout.addWidget(self.label4)
        self.secondRowLayout.addWidget(self.label5)
        self.secondRowLayout.addWidget(self.label6)

        self.label7 = QLabel("RUN Mode: OFF")
        self.label7.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #ff6969;}")
        self.label8 = QLabel("Control Mode: Translational")
        self.label8.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label9 = QLabel("Refrence Frame: base_link")
        self.label9.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.thirdRowLayout.addWidget(self.label7)
        self.thirdRowLayout.addWidget(self.label8)
        self.thirdRowLayout.addWidget(self.label9)

        self.label10 = QLabel("Servo Service: OFF")
        self.label10.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #ff6969;}")
        self.label11 = QLabel("Gripper Position: 0.8")
        self.label11.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.label12 = QLabel("Emergency Stop: OFF")
        self.label12.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #7ab874;}")
        self.fourthRowLayout.addWidget(self.label10)
        self.fourthRowLayout.addWidget(self.label11)
        self.fourthRowLayout.addWidget(self.label12)

        self.label13 = QLabel("Homing Status: OFF")
        self.label13.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        self.fifthRowLayout.addWidget(self.label13)

        # Set the layout and show the window
        self.window.setLayout(self.outerlayout)
        self.window.show()

        # Start a QTimer on gui thread to update values @ 5 Hz
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.ui_update) # type: ignore
        self.timer.start(200)

        # Colors used as label brackgrounds:
        #7ab874 - g
        #ff6969 - r
        #5d6ecf - b

    def ui_update(self):
        # Update the ui on new values received
        self.label1.setText(f"IMU Roll: {self.r}")
        self.label2.setText(f"IMU Pitch: {self.p}")
        self.label3.setText(f"IMU Yaw: {self.y}")
        self.label4.setText(f"VX: {self.vx}")
        self.label5.setText(f"VY: {self.vy}")
        self.label6.setText(f"VZ: {self.vz}")

        self.label7.setText(f"RUN Mode: {self.run_labels[self.run_mode]}")
        if self.run_mode == 0:
            self.label7.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #ff6969;}")
        else:
            self.label7.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #7ab874;}")
        self.label8.setText(f"Control Mode: {self.control_labels[self.control_mode]}")
        self.label9.setText(f"Refrence Frame: {self.ref_labels[self.control_mode]}")

        self.label10.setText(f"Servo Service: {self.run_labels[self.servo_service]}")
        if self.servo_service == 0:
            self.label10.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #ff6969;}")
        else:
            self.label10.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #7ab874;}")
        self.label11.setText("Gripper Position: {:.2f}".format(self.gripper_pos))
        self.label12.setText(f"Emergency Stop: {self.run_labels[self.ir_sw]}")
        if self.ir_sw == 0:
            self.label12.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #7ab874;}")
        else:
            self.label12.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #ff6969;}")
        
        self.label13.setText(f"Homing Status: {self.run_labels[self.homing_status]}")
        if self.homing_status == 0:
            self.label13.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #c4c4c4;}")
        else:
            self.label13.setStyleSheet("QLabel {border: 1px solid black; font-size: 18pt; background-color: #5d6ecf;}")

    def data_receive(self, msg:String):
        # Set local ui variables to incoming new values
        values = msg.data.split(",")
        self.r = float(values[2])
        self.p = float(values[1])
        self.y = float(values[0])
        self.vx = float(values[3])
        self.vy = float(values[4])
        self.vz = float(values[5])
        
        self.run_mode = int(values[6])
        self.control_mode = int(values[7])
        
        self.servo_service = int(values[8])
        self.gripper_pos = float(values[9])
        self.ir_sw = int(values[10])
        if self.ir_sw == 0:
            self.ir_sw = 1
        else:
            self.ir_sw = 0
        
        self.homing_status = int(values[11])

def spin_ros(node):
    rclpy.spin(node)

def main(args=None):
    rclpy.init(args=args)
    gui_node = ControlGui()

    # Start ROS in a separate thread and gui in main thread
    ros_thread = threading.Thread(target=spin_ros, args=(gui_node,), daemon=True)
    ros_thread.start()

    # Exists and shutdowns on keyboard interrupt
    try:
        sys.exit(gui_node.app.exec_())
    finally:
        gui_node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()
