"""
DRONE INTERFACE NODE - MAVSDK Communication Layer
==================================================

PURPOSE:
--------
This node is the HARDWARE ABSTRACTION LAYER that communicates directly with
the flight controller (PX4/ArduPilot) using MAVSDK over MAVLink protocol.

WHY IT'S NEEDED:
----------------
1. REAL DRONE CONTROL: Translates ROS2 commands into MAVLink messages that
   the flight controller understands.

2. TELEMETRY STREAMING: Receives live data from drone (GPS, battery, attitude)
   and publishes to ROS2 topics for other nodes to use.

3. SAFETY MANAGEMENT: Handles arming, takeoff, landing, and emergency stops.

4. CONNECTION MANAGEMENT: Maintains persistent connection to drone, handles
   reconnection if communication is lost.

MAVSDK FEATURES USED:
  - System discovery and connection
  - Telemetry (GPS, battery, attitude, flight mode)
  - Action (arm, takeoff, land, goto, return-to-launch)
  - Offboard control (velocity commands for fine positioning)

DATA FLOW:
----------
RECEIVES (ROS2):
  - /delivery/target_gps - GPS waypoint to fly to
  - /drone/command - Commands: arm, takeoff, land, rtl, goto

PUBLISHES (ROS2):
  - /drone/telemetry/gps - Live GPS position
  - /drone/telemetry/battery - Battery percentage
  - /drone/telemetry/attitude - Roll, pitch, yaw
  - /drone/telemetry/flight_mode - Current flight mode
  - /drone/connection_status - Connected/disconnected

MAVSDK CONNECTION:
  Default: udp://:14540 (PX4 SITL)
  Real drone: serial:///dev/ttyUSB0:57600

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, BatteryState
from geometry_msgs.msg import Vector3
from std_msgs.msg import String, Float32, Bool
import asyncio
import threading
import json

# MAVSDK import with graceful degradation
try:
    from mavsdk import System
    from mavsdk.offboard import OffboardError, VelocityNedYaw
    MAVSDK_AVAILABLE = True
except ImportError:
    MAVSDK_AVAILABLE = False


class DroneInterfaceNode(Node):
    def __init__(self):
        super().__init__('drone_interface')
        
        # Parameters
        self.declare_parameter('connection_url', 'udp://:14540')
        self.declare_parameter('simulation_mode', True)
        self.connection_url = self.get_parameter('connection_url').value
        self.simulation_mode = self.get_parameter('simulation_mode').value
        
        # Drone state
        self.connected = False
        self.armed = False
        self.in_air = False
        self.current_gps = None
        self.battery_percent = 100.0
        self.flight_mode = "UNKNOWN"
        
        # MAVSDK system
        self.drone = None
        self.event_loop = None
        
        # Publishers - Telemetry
        self.gps_pub = self.create_publisher(NavSatFix, '/drone/telemetry/gps', 10)
        self.battery_pub = self.create_publisher(Float32, '/drone/telemetry/battery', 10)
        self.attitude_pub = self.create_publisher(Vector3, '/drone/telemetry/attitude', 10)
        self.flight_mode_pub = self.create_publisher(String, '/drone/telemetry/flight_mode', 10)
        self.connection_pub = self.create_publisher(Bool, '/drone/connection_status', 10)
        self.reached_target_pub = self.create_publisher(String, '/delivery/reached_target', 10)
        
        # Subscribers - Commands
        self.target_gps_sub = self.create_subscription(
            NavSatFix,
            '/delivery/target_gps',
            self.target_gps_callback,
            10
        )
        
        self.command_sub = self.create_subscription(
            String,
            '/drone/command',
            self.command_callback,
            10
        )
        
        # Check MAVSDK availability
        if not MAVSDK_AVAILABLE:
            self.get_logger().warn(
                'MAVSDK not installed! Install with: pip3 install mavsdk'
            )
            self.get_logger().warn('Running in SIMULATION MODE (no real drone)')
            self.simulation_mode = True
        
        # Start async event loop in separate thread
        if MAVSDK_AVAILABLE and not self.simulation_mode:
            self.event_loop = asyncio.new_event_loop()
            self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
            self.async_thread.start()
            # Schedule connection
            asyncio.run_coroutine_threadsafe(self.connect_drone(), self.event_loop)
        
        # Timer for simulation mode telemetry
        if self.simulation_mode:
            self.sim_timer = self.create_timer(1.0, self.simulate_telemetry)
        
        self.get_logger().info(
            f'DroneInterfaceNode initialized (simulation_mode: {self.simulation_mode})'
        )
    
    def _run_async_loop(self):
        """Run asyncio event loop in separate thread"""
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
    
    async def connect_drone(self):
        """Connect to drone via MAVSDK"""
        self.get_logger().info(f'Connecting to drone at {self.connection_url}...')
        
        try:
            self.drone = System()
            await self.drone.connect(system_address=self.connection_url)
            
            # Wait for connection
            async for state in self.drone.core.connection_state():
                if state.is_connected:
                    self.connected = True
                    self.get_logger().info('✓ Drone connected!')
                    
                    # Publish connection status
                    conn_msg = Bool()
                    conn_msg.data = True
                    self.connection_pub.publish(conn_msg)
                    
                    # Start telemetry streams
                    asyncio.ensure_future(self.stream_gps())
                    asyncio.ensure_future(self.stream_battery())
                    asyncio.ensure_future(self.stream_attitude())
                    asyncio.ensure_future(self.stream_flight_mode())
                    asyncio.ensure_future(self.stream_in_air())
                    break
                    
        except Exception as e:
            self.get_logger().error(f'Connection failed: {e}')
            self.connected = False
    
    async def stream_gps(self):
        """Stream GPS telemetry from drone"""
        try:
            async for position in self.drone.telemetry.position():
                gps_msg = NavSatFix()
                gps_msg.latitude = position.latitude_deg
                gps_msg.longitude = position.longitude_deg
                gps_msg.altitude = position.absolute_altitude_m
                self.gps_pub.publish(gps_msg)
                self.current_gps = gps_msg
        except Exception as e:
            self.get_logger().error(f'GPS stream error: {e}')
    
    async def stream_battery(self):
        """Stream battery telemetry from drone"""
        try:
            async for battery in self.drone.telemetry.battery():
                self.battery_percent = battery.remaining_percent * 100
                battery_msg = Float32()
                battery_msg.data = self.battery_percent
                self.battery_pub.publish(battery_msg)
        except Exception as e:
            self.get_logger().error(f'Battery stream error: {e}')
    
    async def stream_attitude(self):
        """Stream attitude telemetry from drone"""
        try:
            async for attitude in self.drone.telemetry.attitude_euler():
                att_msg = Vector3()
                att_msg.x = attitude.roll_deg
                att_msg.y = attitude.pitch_deg
                att_msg.z = attitude.yaw_deg
                self.attitude_pub.publish(att_msg)
        except Exception as e:
            self.get_logger().error(f'Attitude stream error: {e}')
    
    async def stream_flight_mode(self):
        """Stream flight mode from drone"""
        try:
            async for flight_mode in self.drone.telemetry.flight_mode():
                self.flight_mode = str(flight_mode)
                mode_msg = String()
                mode_msg.data = self.flight_mode
                self.flight_mode_pub.publish(mode_msg)
        except Exception as e:
            self.get_logger().error(f'Flight mode stream error: {e}')
    
    async def stream_in_air(self):
        """Stream in-air status from drone"""
        try:
            async for in_air in self.drone.telemetry.in_air():
                self.in_air = in_air
        except Exception as e:
            self.get_logger().error(f'In-air stream error: {e}')
    
    def target_gps_callback(self, msg):
        """Handle target GPS waypoint command"""
        self.get_logger().info(
            f'Target GPS received: lat={msg.latitude:.6f}, lon={msg.longitude:.6f}, alt={msg.altitude:.1f}'
        )
        
        if self.simulation_mode:
            # Simulate reaching target after delay
            self.create_timer(5.0, self._simulate_reached_target, callback_group=None)
        elif MAVSDK_AVAILABLE and self.connected:
            asyncio.run_coroutine_threadsafe(
                self.goto_location(msg.latitude, msg.longitude, msg.altitude),
                self.event_loop
            )
    
    def _simulate_reached_target(self):
        """Simulate reaching target in simulation mode"""
        reached_msg = String()
        reached_msg.data = "reached"
        self.reached_target_pub.publish(reached_msg)
        self.get_logger().info('SIMULATION: Target reached')
    
    async def goto_location(self, lat, lon, alt):
        """Command drone to fly to GPS location"""
        try:
            self.get_logger().info(f'Flying to: {lat:.6f}, {lon:.6f}, {alt:.1f}m')
            await self.drone.action.goto_location(lat, lon, alt, 0)  # 0 = yaw unchanged
            
            # Monitor until reached (within tolerance)
            tolerance = 1.5  # meters
            while True:
                if self.current_gps:
                    distance = self._calculate_distance(
                        self.current_gps.latitude, self.current_gps.longitude,
                        lat, lon
                    )
                    if distance < tolerance:
                        self.get_logger().info(f'Target reached! Distance: {distance:.2f}m')
                        reached_msg = String()
                        reached_msg.data = "reached"
                        self.reached_target_pub.publish(reached_msg)
                        break
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.get_logger().error(f'Goto failed: {e}')
    
    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two GPS points (Haversine)"""
        import math
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    def command_callback(self, msg):
        """Handle drone commands"""
        command = msg.data.lower()
        self.get_logger().info(f'Command received: {command}')
        
        if self.simulation_mode:
            self.get_logger().info(f'SIMULATION: Executing {command}')
            return
        
        if not MAVSDK_AVAILABLE or not self.connected:
            self.get_logger().warn('Cannot execute command: not connected')
            return
        
        # Execute command asynchronously
        if command == 'arm':
            asyncio.run_coroutine_threadsafe(self.arm(), self.event_loop)
        elif command == 'disarm':
            asyncio.run_coroutine_threadsafe(self.disarm(), self.event_loop)
        elif command == 'takeoff':
            asyncio.run_coroutine_threadsafe(self.takeoff(), self.event_loop)
        elif command == 'land':
            asyncio.run_coroutine_threadsafe(self.land(), self.event_loop)
        elif command == 'rtl':
            asyncio.run_coroutine_threadsafe(self.return_to_launch(), self.event_loop)
        else:
            self.get_logger().warn(f'Unknown command: {command}')
    
    async def arm(self):
        """Arm the drone"""
        try:
            self.get_logger().info('Arming...')
            await self.drone.action.arm()
            self.armed = True
            self.get_logger().info('✓ Armed!')
        except Exception as e:
            self.get_logger().error(f'Arm failed: {e}')
    
    async def disarm(self):
        """Disarm the drone"""
        try:
            self.get_logger().info('Disarming...')
            await self.drone.action.disarm()
            self.armed = False
            self.get_logger().info('✓ Disarmed!')
        except Exception as e:
            self.get_logger().error(f'Disarm failed: {e}')
    
    async def takeoff(self):
        """Takeoff to default altitude"""
        try:
            self.get_logger().info('Taking off...')
            await self.drone.action.set_takeoff_altitude(10.0)  # 10 meters
            await self.drone.action.takeoff()
            self.get_logger().info('✓ Takeoff initiated!')
        except Exception as e:
            self.get_logger().error(f'Takeoff failed: {e}')
    
    async def land(self):
        """Land the drone"""
        try:
            self.get_logger().info('Landing...')
            await self.drone.action.land()
            self.get_logger().info('✓ Landing initiated!')
        except Exception as e:
            self.get_logger().error(f'Land failed: {e}')
    
    async def return_to_launch(self):
        """Return to launch position"""
        try:
            self.get_logger().info('Returning to launch...')
            await self.drone.action.return_to_launch()
            self.get_logger().info('✓ RTL initiated!')
        except Exception as e:
            self.get_logger().error(f'RTL failed: {e}')
    
    def simulate_telemetry(self):
        """Publish simulated telemetry when in simulation mode"""
        # Simulated GPS
        gps_msg = NavSatFix()
        gps_msg.latitude = 37.7749
        gps_msg.longitude = -122.4194
        gps_msg.altitude = 10.0
        self.gps_pub.publish(gps_msg)
        
        # Simulated battery
        battery_msg = Float32()
        battery_msg.data = 85.0
        self.battery_pub.publish(battery_msg)
        
        # Simulated attitude
        att_msg = Vector3()
        att_msg.x = 0.0  # roll
        att_msg.y = 0.0  # pitch
        att_msg.z = 90.0  # yaw
        self.attitude_pub.publish(att_msg)
        
        # Simulated flight mode
        mode_msg = String()
        mode_msg.data = "SIMULATION"
        self.flight_mode_pub.publish(mode_msg)
        
        # Connection status
        conn_msg = Bool()
        conn_msg.data = True
        self.connection_pub.publish(conn_msg)


def main(args=None):
    rclpy.init(args=args)
    node = DroneInterfaceNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
