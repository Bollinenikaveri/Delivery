"""
VICTIM COORDINATES SUBSCRIBER NODE - Scout Interface & Goal Validator
======================================================================

PURPOSE:
--------
This node is the BRIDGE between the Scout drone and the Delivery drone.
It receives victim GPS coordinates from Scout, validates the detection
confidence, and creates mission goals for the delivery system.

WHY IT'S NEEDED:
----------------
1. INTER-DRONE COMMUNICATION: Scout drone detects victims and sends GPS.
   This node receives that data via ROS2 topics.

2. CONFIDENCE VALIDATION: Not all detections are reliable. This node
   filters out low-confidence detections (< 0.75 by default) to prevent
   false deliveries.

3. DATA TRANSFORMATION: Converts raw GPS + confidence into a structured
   JSON mission goal that the action_server can process.

4. DECOUPLING: Separates Scout communication from mission execution,
   allowing different Scout implementations without changing delivery logic.

DATA FLOW:
----------
RECEIVES (from Scout drone):
  - /scout/victim_gps (NavSatFix) - Latitude, longitude, altitude of victim
  - /scout/detection_confidence (Float32) - Detection confidence 0.0-1.0

PUBLISHES:
  - /delivery/mission_goal (String/JSON) - Validated mission target

PARAMETERS:
  - confidence_threshold: 0.75 (minimum confidence to accept detection)

EXAMPLE MISSION GOAL JSON:
{
    "latitude": 37.7749,
    "longitude": -122.4194,
    "altitude": 10.0,
    "confidence": 0.92,
    "timestamp": "..."
}

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Float32, String
import json


class VictimCoordinatesSubscriberNode(Node):
    def __init__(self):
        super().__init__('victim_coordinates_subscriber')
        
        # Get confidence threshold from parameters
        self.declare_parameter('confidence_threshold', 0.75)
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        
        self.latest_victim_gps = None
        self.latest_confidence = None
        
        # Subscribers
        self.victim_gps_sub = self.create_subscription(
            NavSatFix,
            '/scout/victim_gps',
            self.victim_gps_callback,
            10
        )
        
        self.detection_confidence_sub = self.create_subscription(
            Float32,
            '/scout/detection_confidence',
            self.detection_confidence_callback,
            10
        )
        
        # Publisher
        self.mission_goal_pub = self.create_publisher(
            String,
            '/delivery/mission_goal',
            10
        )
        
        self.get_logger().info(
            f'VictimCoordinatesSubscriberNode initialized (confidence_threshold: {self.confidence_threshold})'
        )
    
    def victim_gps_callback(self, msg):
        """Receive victim GPS coordinates from Scout"""
        self.latest_victim_gps = msg
        self.get_logger().debug(
            f'Victim GPS received: lat={msg.latitude}, lon={msg.longitude}, alt={msg.altitude}'
        )
        self.try_publish_mission_goal()
    
    def detection_confidence_callback(self, msg):
        """Receive detection confidence from Scout"""
        self.latest_confidence = msg.data
        self.get_logger().debug(f'Detection confidence received: {self.latest_confidence}')
        self.try_publish_mission_goal()
    
    def try_publish_mission_goal(self):
        """Publish mission goal if both GPS and confidence are valid"""
        if self.latest_victim_gps is None or self.latest_confidence is None:
            return
        
        # Validate confidence threshold
        if self.latest_confidence < self.confidence_threshold:
            self.get_logger().warn(
                f'Detection confidence {self.latest_confidence} below threshold {self.confidence_threshold}'
            )
            return
        
        # Create mission goal JSON
        mission_goal = {
            'latitude': float(self.latest_victim_gps.latitude),
            'longitude': float(self.latest_victim_gps.longitude),
            'altitude': float(self.latest_victim_gps.altitude),
            'confidence': float(self.latest_confidence),
            'timestamp': str(self.get_clock().now()),
        }
        
        # Publish mission goal
        goal_msg = String()
        goal_msg.data = json.dumps(mission_goal)
        self.mission_goal_pub.publish(goal_msg)
        
        self.get_logger().info(
            f'Mission goal published: lat={self.latest_victim_gps.latitude:.6f}, '
            f'lon={self.latest_victim_gps.longitude:.6f}, confidence={self.latest_confidence:.2f}'
        )
        
        # Reset to avoid republishing same goal
        self.latest_victim_gps = None
        self.latest_confidence = None


def main(args=None):
    rclpy.init(args=args)
    node = VictimCoordinatesSubscriberNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
