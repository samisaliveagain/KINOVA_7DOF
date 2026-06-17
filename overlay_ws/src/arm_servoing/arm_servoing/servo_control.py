from math import copysign
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from control_msgs.action import GripperCommand
from rclpy.action import ActionClient
from std_srvs.srv import Trigger
import time
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

class ServoControl(Node):
    def __init__(self):
        super().__init__('servo_control')

        self.declare_parameter("vel_scale", 0.2)
        self.vel_scale: float = self.get_parameter("vel_scale").get_parameter_value().double_value

        # Clients for the servo service
        self.start_client = self.create_client(Trigger, '/servo_node/start_servo')
        self.stop_client = self.create_client(Trigger, '/servo_node/stop_servo')

        # Servo, Joint Controller and UI data publishers
        self.init_pub = self.create_publisher(JointTrajectory, '/joint_trajectory_controller/joint_trajectory', 10)
        self.pub = self.create_publisher(TwistStamped, '/servo_node/delta_twist_cmds', 10)
        self.ui_pub = self.create_publisher(String, '/servo_control/ui_data', 10)
        
        # The gripper is controlled using an Action Client
        self.gripper_client = ActionClient(self, GripperCommand, '/robotiq_gripper_controller/gripper_cmd')
        
        # Create subscriptions for the sensor data topics
        self.imu_sub = self.create_subscription(String, '/wifi/imu', self.imu_receive, 10)
        self.enc_sub = self.create_subscription(String, '/wifi/enc', self.enc_receive, 10)

        # Timer to send servo commands
        self.timer = self.create_timer(0.1, self.send_servo_cmd)

        # Control Variables
        self.control_labels = ["Translation", "Orientation", "Gripper"]
        self.angle_step1 = 20.0 * 3.141 / 180.0
        self.angle_step2 = 30.0 * 3.141 / 180.0
        self.home_angle = -45.0 * 3.141 / 180.0
        self.control_mode = 0
        self.run_mode = 0
        self.control_sw = 0
        self.ir_sw = 0
        self.use_sw = True
        self.gripper_pos = 0.8
        self.r = 0.0
        self.p = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.vz = 0.0
        self.servo_service = 0
        self.homing_status = 0

        # Set starting home position
        self.send_home()

        # Log control mode
        self.get_logger().info(f"Run Mode changed to: {self.run_mode}.")
        self.get_logger().info(f"Control Mode changed to: {self.control_mode}.      Now controlling: {self.control_labels[self.control_mode]}")

    def start_servo_service(self):
        # Wait for servo start service and send trigger
        if not self.start_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().info("Start servo service not available!")
        req = Trigger.Request()
        future = self.start_client.call_async(req)

        # Update the servo service state
        self.servo_service = 1

    def stop_servo_service(self):
        # Wait for servo stop service and send trigger
        if not self.stop_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("Stop servo service not available!")
        req2 = Trigger.Request()
        future2 = self.stop_client.call_async(req2)

        # Update the servo service state
        self.servo_service = 0

    def imu_receive(self, msg:String):
        # Receive IMU data and set to local variables
        data = msg.data
        values = data.split(",")
        self.r = float(values[0])
        self.p = float(values[1])
        self.y = float(values[2])
    
    def enc_receive(self, msg:String):
        # Receive Encoder data and set to local variables
        data = msg.data
        values = data.split(",")
        # Control Mode
        if int(values[0]) != self.control_mode:
            self.control_mode = int(values[0])
            self.get_logger().info(f"Control Mode changed to: {self.control_mode}.      Now controlling: {self.control_labels[self.control_mode]}")
            if self.control_mode == 0:
                self.get_logger().info("Refrence Frame changed to: 'base_link'")
            elif self.control_mode == 1:
                self.get_logger().info("Refrence Frame changed to: 'end_effector_link'")
        
        # Emergency Stop
        self.ir_sw = int(values[2])

        # Run Mode (when not homing)
        if self.run_mode != int(values[1]) and int(values[3]) != 1:
            self.run_mode = int(values[1])
            self.get_logger().info(f"Run Mode changed to: {self.run_mode}.")

        # Homing command detection and latch using use_sw boolean
        # Latching is needed cause homing runs for 3 seconds and the user doesn't need to hold
        # the encoder button for the complete duration.
        if int(values[3]) == 1 and self.use_sw:
            self.run_mode = 0
            self.use_sw = False
            self.get_logger().info(f"Run Mode changed to: {self.run_mode} for homing.")
            self.send_home(t=10)
        if int(values[3]) == 0 and not self.use_sw:
            self.use_sw = True
    
    def publish_ui_data(self):
        data = str(self.r) + "," + str(self.p) + "," + str(self.y) + "," + str(self.vx) + "," + str(self.vy) + "," + str(self.vz)
        data += "," + str(self.run_mode) + "," + str(self.control_mode) + "," + str(self.servo_service) + "," + str(self.gripper_pos) + "," + str(self.ir_sw)
        data += "," + str(self.homing_status)
        ui_msg = String()
        ui_msg.data = data
        self.ui_pub.publish(ui_msg)

    def send_home(self, t = 10):
        # Stop the servo service before sending joint states
        # Sending joint states while the servo service is running causes the position to reset
        # to before homing when new twist command is sent to the servo service.
        self.get_logger().info("Stopping Servo Service")
        self.stop_servo_service()

        # Set the homing status and publish the ui data
        self.homing_status = 1
        self.publish_ui_data()

        # Create the homing position and publish to joints_controller
        msg = JointTrajectory()
        msg.joint_names = ["joint_1","joint_2","joint_3","joint_4","joint_5","joint_6","joint_7"]
        pt = JointTrajectoryPoint()
        pt.positions = [4*0.017, 7*0.017, -176*0.017, -121*0.017, -3*0.017, -39*0.017, 99*0.017]
        pt.time_from_start.sec = int(t)
        pt.time_from_start.nanosec = int((0) * 1e9)
        msg.points = [pt]
        self.init_pub.publish(msg)

        # Log and wait 1 sec more - till the robot reaches homing position
        self.get_logger().info(f"!!! Homing !!!")
        time.sleep(t+1)

        # Restart the servo service and reset homing status
        self.start_servo_service()
        self.get_logger().info("Started Servo Service")
        self.homing_status = 0


    def send_servo_cmd(self):
        # Check for Emergency Switch
        if self.ir_sw == 0:
            self.run_mode = 0
            self.get_logger().warn(f"!!! EMERGENCY STOP DETECTED !!!.")
            self.get_logger().warn(f"Run Mode changed to: {self.run_mode}.")

        # Calculate the directional velocities in angle steps.
        self.vx = ((abs(self.r) > self.angle_step1) * 0.15 + (abs(self.r) > self.angle_step2) * 0.15) * copysign(self.vel_scale, self.r)
        self.vy = ((abs(self.y) > self.angle_step1) * 0.15 + (abs(self.y) > self.angle_step2) * 0.15) * copysign(self.vel_scale, self.y)
        self.vz = ((abs(self.p) > self.angle_step1) * 0.15 + (abs(self.p) > self.angle_step2) * 0.15) * copysign(self.vel_scale, self.p)

        # Create a zero twist message
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = 0.0
        msg.twist.linear.y = 0.0
        msg.twist.linear.z = 0.0
        msg.twist.angular.x = 0.0
        msg.twist.angular.y = 0.0
        msg.twist.angular.z = 0.0

        # Edit the message components based on control mode and publish
        if self.run_mode == 1 and self.ir_sw == 1:
            if self.control_mode == 0:          # Translation
                msg.header.frame_id = 'base_link'
                msg.twist.linear.x = self.vx
                msg.twist.linear.y = self.vy
                msg.twist.linear.z = self.vz
                msg.twist.angular.x = 0.0
                msg.twist.angular.y = 0.0
                msg.twist.angular.z = 0.0
            elif self.control_mode == 1:        # Orientation
                msg.header.frame_id = 'end_effector_link'
                msg.twist.linear.x = 0.0
                msg.twist.linear.y = 0.0
                msg.twist.linear.z = 0.0
                msg.twist.angular.x = self.vx * 3.0
                msg.twist.angular.y = self.vz * 3.0
                msg.twist.angular.z = self.vy * 3.0
        
        self.pub.publish(msg)

        # Handle the gripper control
        if self.run_mode == 1 and self.ir_sw == 1:
            if self.control_mode == 2:                
                self.gripper_pos = self.gripper_pos + self.vx * 0.2
                if self.gripper_pos < 0:
                    self.gripper_pos = 0.0
                if self.gripper_pos > 0.8:
                    self.gripper_pos = 0.8
                
                # create GripperGoal command and sent to the action client
                gc = GripperCommand.Goal()
                gc.command.position = self.gripper_pos
                gc.command.max_effort = 100.0
                send_goal_future = self.gripper_client.send_goal_async(gc)
                

        # Publish UI data
        self.publish_ui_data()

        # Reset RPY for next loop
        # Incase the sensor data stops coming, the robot won't be stuck moving based on last velocities. 
        self.r = 0.0
        self.p = 0.0
        self.y = 0.0
        

def main():
    rclpy.init()
    node = ServoControl()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
