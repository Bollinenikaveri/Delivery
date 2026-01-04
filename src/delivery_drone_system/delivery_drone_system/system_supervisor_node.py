"""
SYSTEM SUPERVISOR NODE - Health Monitoring & Watchdog
======================================================

PURPOSE:
--------
This node acts as a WATCHDOG that continuously monitors the health of the 
entire delivery drone system and reports status to ground control.

WHY IT'S NEEDED:
----------------
1. SAFETY MONITORING: In autonomous systems, failures must be detected early.
   This node tracks battery, GPS, camera, motors, and mission state.

2. FAULT DETECTION: If any subsystem fails (e.g., GPS lock lost, camera offline),
   this node can alert operators or trigger emergency procedures.

3. TELEMETRY: Ground control needs real-time visibility into drone health.
   This node publishes periodic health reports for monitoring dashboards.

4. MISSION AWARENESS: By subscribing to mission state, it knows if the drone
   is idle, navigating, dropping payload, etc. - useful for diagnostics.

DATA FLOW:
----------
RECEIVES:
  - /delivery/mission_state (from action_server) - Current mission phase

PUBLISHES:
  - /delivery/system_health - JSON with battery, GPS, camera, motor status

HEALTH CHECK INTERVAL: Every 2 seconds

SIMULATED METRICS (for demo):
  - Battery level: 85%
  - GPS lock: True
  - Camera online: True
  - Motor status: OPERATIONAL

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import json


class SystemSupervisorNode(Node):
    def __init__(self):
        super().__init__('system_supervisor')
        
        # System health state
        self.system_healthy = True
        self.mission_state = None
        self.health_check_count = 0
        
        # Subscriber
        self.mission_state_sub = self.create_subscription(
            String,
            '/delivery/mission_state',
            self.mission_state_callback,
            10
        )
        
        # Publisher
        self.system_health_pub = self.create_publisher(
            String,
            '/delivery/system_health',
            10
        )
        
        # Timer for periodic health checks
        self.health_check_timer = self.create_timer(2.0, self.health_check)
        
        self.get_logger().info('SystemSupervisorNode initialized')
    
    def mission_state_callback(self, msg):
        """Monitor mission state"""
        self.mission_state = msg.data
        self.get_logger().debug(f'Mission state updated: {self.mission_state}')
    
    def health_check(self):
        """Perform periodic health checks"""
        self.health_check_count += 1
        
        # Simple health check logic
        # In a real system, this would check:
        # - Battery level
        # - Communication status
        # - Sensor health
        # - Motor status
        # etc.
        
        health_status = {
            'timestamp': str(self.get_clock().now()),
            'system_healthy': self.system_healthy,
            'mission_state': self.mission_state or 'IDLE',
            'health_check_count': self.health_check_count,
            'battery_level': 85.0,  # Simulated
            'gps_lock': True,  # Simulated
            'camera_online': True,  # Simulated
            'motor_status': 'OPERATIONAL',  # Simulated
        }
        
        # Publish health status
        health_msg = String()
        health_msg.data = json.dumps(health_status)
        self.system_health_pub.publish(health_msg)
        
        self.get_logger().info(
            f'Health check #{self.health_check_count}: System {"HEALTHY" if self.system_healthy else "UNHEALTHY"}'
        )


def main(args=None):
    rclpy.init(args=args)
    node = SystemSupervisorNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
