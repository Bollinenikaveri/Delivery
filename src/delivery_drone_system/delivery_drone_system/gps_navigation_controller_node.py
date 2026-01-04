"""
GPS NAVIGATION CONTROLLER NODE - Autonomous Flight Navigation
==============================================================

PURPOSE:
--------
This node handles AUTONOMOUS NAVIGATION of the delivery drone from its
current position to the target victim GPS coordinates.

WHY IT'S NEEDED:
----------------
1. GPS WAYPOINT NAVIGATION: The drone must fly to exact coordinates where
   the victim was detected. This node manages that flight path.

2. DISTANCE CALCULATION: Uses Haversine formula to calculate real-world
   distance between current position and target (accounts for Earth's curvature).

3. ARRIVAL DETECTION: Determines when the drone is "close enough" to the
   target (within 1.5m tolerance) and signals the next phase can begin.

4. FLIGHT SIMULATION: In simulation mode, gradually moves drone position
   toward target to mimic real flight behavior.

DATA FLOW:
----------
RECEIVES:
  - /delivery/target_gps (NavSatFix) - Target coordinates from action_server

PUBLISHES:
  - /delivery/reached_target (String) - "reached" when within tolerance

PARAMETERS:
  - target_tolerance_m: 1.5 (meters - how close is "arrived")

NAVIGATION ALGORITHM:
  1. Receive target GPS coordinates
  2. Calculate distance using Haversine formula
  3. Simulate movement toward target (10% closer each 0.5s)
  4. When distance <= tolerance, publish "reached"

HAVERSINE FORMULA:
  - Calculates great-circle distance between two GPS points
  - Accounts for Earth's spherical shape
  - Returns distance in meters

REAL-WORLD INTEGRATION:
  In production, this would interface with:
  - PX4/ArduPilot flight controller
  - MAVLink protocol
  - GPS receiver hardware

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import String
import math


class GPSNavigationControllerNode(Node):
    def __init__(self):
        super().__init__('gps_navigation_controller')
        
        # Get target tolerance from parameters
        self.declare_parameter('target_tolerance_m', 1.5)
        self.target_tolerance = self.get_parameter('target_tolerance_m').value
        
        # Navigation state
        self.target_gps = None
        self.current_gps = None  # Simulated
        self.reached_target_published = False
        
        # Subscribers
        self.target_gps_sub = self.create_subscription(
            NavSatFix,
            '/delivery/target_gps',
            self.target_gps_callback,
            10
        )
        
        self.reached_target_trigger_sub = self.create_subscription(
            String,
            '/delivery/reached_target',
            self.reached_target_trigger_callback,
            10
        )
        
        # Publisher
        self.reached_target_pub = self.create_publisher(
            String,
            '/delivery/reached_target',
            10
        )
        
        # Timer for navigation simulation
        self.nav_timer = self.create_timer(0.5, self.simulate_navigation)
        
        self.get_logger().info(
            f'GPSNavigationControllerNode initialized (target_tolerance: {self.target_tolerance}m)'
        )
    
    def target_gps_callback(self, msg):
        """Receive target GPS coordinates"""
        self.target_gps = msg
        self.reached_target_published = False
        self.get_logger().info(
            f'Target GPS set: lat={msg.latitude:.6f}, lon={msg.longitude:.6f}, alt={msg.altitude:.2f}'
        )
    
    def reached_target_trigger_callback(self, msg):
        """Handle reached target trigger (for feedback)"""
        self.get_logger().debug('Reached target trigger received')
    
    def simulate_navigation(self):
        """Simulate GPS navigation towards target"""
        if self.target_gps is None or self.reached_target_published:
            return
        
        # Simulate gradual approach to target
        if self.current_gps is None:
            # Start from current location (simulated offset)
            self.current_gps = NavSatFix()
            self.current_gps.latitude = self.target_gps.latitude + 0.001
            self.current_gps.longitude = self.target_gps.longitude + 0.001
            self.current_gps.altitude = self.target_gps.altitude
        else:
            # Move towards target (simulated navigation)
            move_factor = 0.1  # Move 10% closer each iteration
            self.current_gps.latitude = (
                self.current_gps.latitude * (1 - move_factor) +
                self.target_gps.latitude * move_factor
            )
            self.current_gps.longitude = (
                self.current_gps.longitude * (1 - move_factor) +
                self.target_gps.longitude * move_factor
            )
            self.current_gps.altitude = self.target_gps.altitude
        
        # Calculate distance to target
        distance = self.calculate_distance(self.current_gps, self.target_gps)
        
        self.get_logger().debug(
            f'Distance to target: {distance:.2f}m (current: {self.current_gps.latitude:.6f}, '
            f'{self.current_gps.longitude:.6f})'
        )
        
        # Check if within tolerance
        if distance <= self.target_tolerance:
            self.reached_target_published = True
            reached_msg = String()
            reached_msg.data = "reached"
            self.reached_target_pub.publish(reached_msg)
            
            self.get_logger().info(
                f'Target reached! Distance: {distance:.2f}m (tolerance: {self.target_tolerance}m)'
            )
    
    def calculate_distance(self, gps1, gps2):
        """
        Calculate distance between two GPS coordinates using Haversine formula
        Returns distance in meters (approximate)
        """
        lat1, lon1 = math.radians(gps1.latitude), math.radians(gps1.longitude)
        lat2, lon2 = math.radians(gps2.latitude), math.radians(gps2.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371000  # Earth radius in meters
        
        return c * r


def main(args=None):
    rclpy.init(args=args)
    node = GPSNavigationControllerNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
