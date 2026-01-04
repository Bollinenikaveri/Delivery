"""
TELEMETRY MONITOR NODE - Live Drone Data Dashboard
====================================================

PURPOSE:
--------
This node aggregates all telemetry data from the drone and provides a
unified monitoring interface for ground control operators.

WHY IT'S NEEDED:
----------------
1. DATA AGGREGATION: Collects GPS, battery, attitude, and flight mode
   from drone_interface_node into a single comprehensive status.

2. ALERT SYSTEM: Monitors critical parameters and triggers warnings:
   - Low battery (< 20%)
   - GPS signal loss
   - Unusual attitude angles
   - Communication timeout

3. LOGGING: Records flight data for post-mission analysis and debugging.

4. GROUND CONTROL INTERFACE: Publishes combined status JSON that can be
   displayed on operator dashboards.

DATA FLOW:
----------
RECEIVES:
  - /drone/telemetry/gps - Live GPS position
  - /drone/telemetry/battery - Battery percentage
  - /drone/telemetry/attitude - Roll, pitch, yaw
  - /drone/telemetry/flight_mode - Current flight mode
  - /drone/connection_status - Connection state
  - /delivery/mission_state - Current mission phase

PUBLISHES:
  - /drone/telemetry/combined - All telemetry as JSON
  - /drone/alerts - Critical alerts and warnings

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import Vector3
from std_msgs.msg import String, Float32, Bool
import json
from datetime import datetime


class TelemetryMonitorNode(Node):
    def __init__(self):
        super().__init__('telemetry_monitor')
        
        # Parameters
        self.declare_parameter('low_battery_threshold', 20.0)
        self.declare_parameter('critical_battery_threshold', 10.0)
        self.declare_parameter('max_attitude_angle', 45.0)
        self.low_battery = self.get_parameter('low_battery_threshold').value
        self.critical_battery = self.get_parameter('critical_battery_threshold').value
        self.max_angle = self.get_parameter('max_attitude_angle').value
        
        # Telemetry state
        self.telemetry = {
            'timestamp': None,
            'connected': False,
            'gps': {'latitude': 0.0, 'longitude': 0.0, 'altitude': 0.0},
            'battery_percent': 0.0,
            'attitude': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
            'flight_mode': 'UNKNOWN',
            'mission_state': 'IDLE',
            'alerts': []
        }
        
        self.last_update_time = self.get_clock().now()
        
        # Subscribers
        self.gps_sub = self.create_subscription(
            NavSatFix, '/drone/telemetry/gps', self.gps_callback, 10)
        
        self.battery_sub = self.create_subscription(
            Float32, '/drone/telemetry/battery', self.battery_callback, 10)
        
        self.attitude_sub = self.create_subscription(
            Vector3, '/drone/telemetry/attitude', self.attitude_callback, 10)
        
        self.flight_mode_sub = self.create_subscription(
            String, '/drone/telemetry/flight_mode', self.flight_mode_callback, 10)
        
        self.connection_sub = self.create_subscription(
            Bool, '/drone/connection_status', self.connection_callback, 10)
        
        self.mission_state_sub = self.create_subscription(
            String, '/delivery/mission_state', self.mission_state_callback, 10)
        
        # Publishers
        self.combined_pub = self.create_publisher(String, '/drone/telemetry/combined', 10)
        self.alert_pub = self.create_publisher(String, '/drone/alerts', 10)
        
        # Timer for publishing combined telemetry
        self.publish_timer = self.create_timer(1.0, self.publish_combined_telemetry)
        
        # Timer for checking alerts
        self.alert_timer = self.create_timer(2.0, self.check_alerts)
        
        self.get_logger().info('TelemetryMonitorNode initialized')
    
    def gps_callback(self, msg):
        """Update GPS telemetry"""
        self.telemetry['gps'] = {
            'latitude': msg.latitude,
            'longitude': msg.longitude,
            'altitude': msg.altitude
        }
        self.last_update_time = self.get_clock().now()
    
    def battery_callback(self, msg):
        """Update battery telemetry"""
        self.telemetry['battery_percent'] = msg.data
        self.last_update_time = self.get_clock().now()
    
    def attitude_callback(self, msg):
        """Update attitude telemetry"""
        self.telemetry['attitude'] = {
            'roll': msg.x,
            'pitch': msg.y,
            'yaw': msg.z
        }
        self.last_update_time = self.get_clock().now()
    
    def flight_mode_callback(self, msg):
        """Update flight mode"""
        self.telemetry['flight_mode'] = msg.data
        self.last_update_time = self.get_clock().now()
    
    def connection_callback(self, msg):
        """Update connection status"""
        self.telemetry['connected'] = msg.data
        self.last_update_time = self.get_clock().now()
    
    def mission_state_callback(self, msg):
        """Update mission state"""
        self.telemetry['mission_state'] = msg.data
    
    def publish_combined_telemetry(self):
        """Publish all telemetry as combined JSON"""
        self.telemetry['timestamp'] = datetime.now().isoformat()
        
        combined_msg = String()
        combined_msg.data = json.dumps(self.telemetry, indent=2)
        self.combined_pub.publish(combined_msg)
        
        # Log summary
        gps = self.telemetry['gps']
        self.get_logger().debug(
            f"GPS: {gps['latitude']:.6f}, {gps['longitude']:.6f} | "
            f"Battery: {self.telemetry['battery_percent']:.1f}% | "
            f"Mode: {self.telemetry['flight_mode']}"
        )
    
    def check_alerts(self):
        """Check for critical conditions and publish alerts"""
        alerts = []
        
        # Check battery
        battery = self.telemetry['battery_percent']
        if battery < self.critical_battery:
            alerts.append({
                'level': 'CRITICAL',
                'message': f'CRITICAL BATTERY: {battery:.1f}%',
                'action': 'IMMEDIATE LANDING REQUIRED'
            })
        elif battery < self.low_battery:
            alerts.append({
                'level': 'WARNING',
                'message': f'Low battery: {battery:.1f}%',
                'action': 'Consider returning to base'
            })
        
        # Check attitude
        attitude = self.telemetry['attitude']
        if abs(attitude['roll']) > self.max_angle or abs(attitude['pitch']) > self.max_angle:
            alerts.append({
                'level': 'WARNING',
                'message': f"Unusual attitude: roll={attitude['roll']:.1f}°, pitch={attitude['pitch']:.1f}°",
                'action': 'Check wind conditions'
            })
        
        # Check connection timeout
        time_since_update = (self.get_clock().now() - self.last_update_time).nanoseconds / 1e9
        if time_since_update > 5.0:
            alerts.append({
                'level': 'WARNING',
                'message': f'No telemetry update for {time_since_update:.1f}s',
                'action': 'Check drone connection'
            })
        
        # Check GPS
        gps = self.telemetry['gps']
        if gps['latitude'] == 0.0 and gps['longitude'] == 0.0:
            alerts.append({
                'level': 'WARNING',
                'message': 'No GPS fix',
                'action': 'Wait for GPS lock'
            })
        
        # Update and publish alerts
        self.telemetry['alerts'] = alerts
        
        if alerts:
            alert_msg = String()
            alert_msg.data = json.dumps(alerts)
            self.alert_pub.publish(alert_msg)
            
            for alert in alerts:
                if alert['level'] == 'CRITICAL':
                    self.get_logger().error(f"🚨 {alert['message']}")
                else:
                    self.get_logger().warn(f"⚠️ {alert['message']}")


def main(args=None):
    rclpy.init(args=args)
    node = TelemetryMonitorNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
