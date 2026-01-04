import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Get package directory
    pkg_dir = get_package_share_directory('delivery_drone_system')
    config_file = os.path.join(pkg_dir, 'config', 'delivery_config.yaml')
    
    # Launch arguments
    simulation_mode_arg = DeclareLaunchArgument(
        'simulation_mode',
        default_value='true',
        description='Run in simulation mode (no real drone connection)'
    )
    
    connection_url_arg = DeclareLaunchArgument(
        'connection_url',
        default_value='udp://:14540',
        description='MAVSDK connection URL (udp://:14540 for SITL, serial:///dev/ttyUSB0:57600 for real)'
    )
    
    # Launch description
    ld = LaunchDescription()
    
    # Add launch arguments
    ld.add_action(simulation_mode_arg)
    ld.add_action(connection_url_arg)
    
    # ============== MAVSDK NODES (Hardware Interface) ==============
    
    # Drone Interface - MAVSDK communication (FIRST - provides telemetry)
    drone_interface = Node(
        package='delivery_drone_system',
        executable='drone_interface',
        name='drone_interface',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'simulation_mode': LaunchConfiguration('simulation_mode'),
            'connection_url': LaunchConfiguration('connection_url'),
        }],
    )
    
    # Telemetry Monitor - Aggregates all drone data
    telemetry_monitor = Node(
        package='delivery_drone_system',
        executable='telemetry_monitor',
        name='telemetry_monitor',
        output='screen',
        emulate_tty=True,
        parameters=[config_file],
    )
    
    # ============== MISSION CONTROL NODES ==============
    
    # Action Server (FSM Coordinator)
    action_server = Node(
        package='delivery_drone_system',
        executable='action_server',
        name='action_server',
        output='screen',
        emulate_tty=True,
    )
    
    # System Supervisor
    system_supervisor = Node(
        package='delivery_drone_system',
        executable='system_supervisor',
        name='system_supervisor',
        output='screen',
        emulate_tty=True,
    )
    
    # Victim Coordinates Subscriber
    victim_coordinates_subscriber = Node(
        package='delivery_drone_system',
        executable='victim_coordinates_subscriber',
        name='victim_coordinates_subscriber',
        output='screen',
        emulate_tty=True,
        parameters=[config_file],
    )
    
    # GPS Navigation Controller
    gps_navigation_controller = Node(
        package='delivery_drone_system',
        executable='gps_navigation_controller',
        name='gps_navigation_controller',
        output='screen',
        emulate_tty=True,
        parameters=[config_file],
    )
    
    # Visual Alignment
    visual_alignment = Node(
        package='delivery_drone_system',
        executable='visual_alignment',
        name='visual_alignment',
        output='screen',
        emulate_tty=True,
    )
    
    # Victim Confirmation
    victim_confirmation = Node(
        package='delivery_drone_system',
        executable='victim_confirmation',
        name='victim_confirmation',
        output='screen',
        emulate_tty=True,
    )
    
    # Payload Drop Controller
    payload_drop_controller = Node(
        package='delivery_drone_system',
        executable='payload_drop_controller',
        name='payload_drop_controller',
        output='screen',
        emulate_tty=True,
    )
    
    # Add nodes to launch description in proper order
    # MAVSDK nodes first (hardware layer)
    ld.add_action(drone_interface)
    ld.add_action(telemetry_monitor)
    
    # Mission control nodes
    ld.add_action(action_server)
    ld.add_action(system_supervisor)
    ld.add_action(victim_coordinates_subscriber)
    ld.add_action(gps_navigation_controller)
    ld.add_action(visual_alignment)
    ld.add_action(victim_confirmation)
    ld.add_action(payload_drop_controller)
    
    return ld
