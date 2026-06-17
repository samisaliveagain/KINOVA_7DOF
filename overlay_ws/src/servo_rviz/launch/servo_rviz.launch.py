from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_param_builder import ParameterBuilder
from launch_ros.actions import Node
from launch.conditions import IfCondition
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # declare launch command arguments and parameters for nodes launch prameters
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument(
            "bind_ip",
            default_value="10.65.127.91",
            description="IP address to bind UDP socket."
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "port",
            default_value="5000",
            description="UDP port.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "delay",
            default_value="3.0",
            description="Delay (seconds) before starting RViz & Servo.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "launch_ui",
            default_value="true",
            description="True if display gui should be launched together with RViz.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "robot_ip",
            default_value="192.168.1.10",
            description="True if display gui should be launched together with RViz.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="true",
            description="True if display gui should be launched together with RViz.",
        )
    )
    declared_arguments.append(
        DeclareLaunchArgument(
            "vel_scale",
            default_value="0.2",
            description="True if display gui should be launched together with RViz.",
        )
    )

    bind_ip = LaunchConfiguration("bind_ip")
    port = LaunchConfiguration("port")
    startup_delay = LaunchConfiguration("delay")
    launch_ui = LaunchConfiguration("launch_ui")
    robot_ip = LaunchConfiguration("robot_ip")
    use_sim_time = LaunchConfiguration("use_sim_time")
    vel_scale = LaunchConfiguration("vel_scale")
    
    # Paths to existing launch files for fake hardware and moveit sim (in colcon_ws)
    kortex_bringup_launch = os.path.join(
        get_package_share_directory("kortex_bringup"),
        "launch",
        "gen3.launch.py",
    )

    moveit_sim_launch = os.path.join(
        get_package_share_directory("kinova_gen3_7dof_robotiq_2f_85_moveit_config"),
        "launch",
        "sim.launch.py",
    )

    # First launch: fake hardware
    gen3_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(kortex_bringup_launch),
        launch_arguments={
            "robot_ip": robot_ip,
            "use_fake_hardware": "true",
            "launch_rviz": "false",
        }.items(),
    )

    # Second launch: moveit sim
    sim_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(moveit_sim_launch),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "launch_rviz": "true",
        }.items(),
    )

    # Full path to servo config
    servo_yaml_path = os.path.join(
        get_package_share_directory("servo_rviz"),
        "config",
        "gen3_servo_config.yaml"
    )

    # Load the servo config as a parameters dictionary
    servo_params = {
        "moveit_servo": ParameterBuilder("moveit_servo")
        .yaml(servo_yaml_path)
        .to_dict()
    }

    # Servo Node
    servo_node = Node(
        package="moveit_servo",
        executable="servo_node_main",
        name="servo_node",
        output="screen",
        parameters=[
            servo_params,  # YAML parsed by ROS2
            # moveit_config["robot_description"],
            # moveit_config["robot_description_semantic"],
            # moveit_config["robot_description_kinematics"],
        ],
        arguments=["--ros-args", "--log-level", "info"],
    )

    # UDP Bridge Node
    wifi_node = Node(
        package="wifi_sensor_bridge",
        executable="udp_sensor_receiver",
        name="udp_sensor_receiver",
        output="screen",
        parameters=[{
            "bind_ip": bind_ip,
            "port": port,
        }],
    )

    # Arm Servoing Control Node
    control_node = Node(
        package="arm_servoing",
        executable="servo_control",
        name="servo_control",
        output="screen",
        parameters=[{
            "vel_scale": vel_scale,
        }],
    )

    #GUI Node
    control_gui_node = Node(
        package="control_gui",
        executable="control_gui",
        name="control_gui",
        output="screen",
        condition=IfCondition(launch_ui),
    )

    # Delay MoveItSim launch to allow controllers to be ready
    delayed_sim_launch = TimerAction(
        period=startup_delay,
        actions=[sim_launch, servo_node, wifi_node, control_node, control_gui_node],
    )

    return LaunchDescription(declared_arguments + [gen3_launch, delayed_sim_launch])