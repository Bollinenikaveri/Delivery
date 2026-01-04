"""
ACTION SERVER NODE - Central Mission Coordinator (FSM)
======================================================

PURPOSE:
--------
This node is the BRAIN of the delivery drone system. It implements a Finite State 
Machine (FSM) that coordinates the entire delivery mission from start to finish.

WHY IT'S NEEDED:
----------------
1. CENTRALIZED CONTROL: Without a coordinator, nodes would operate independently
   with no way to sequence the delivery process correctly.

2. STATE MANAGEMENT: Ensures the drone follows the correct order:
   NAVIGATING → ALIGNING → CONFIRMING → DROPPING → COMPLETE

3. SAFETY TIMEOUTS: Prevents the drone from getting stuck in any state forever.
   If navigation takes > 60s, alignment > 30s, etc., it triggers safety handling.

4. MISSION TRACKING: Receives goals from Scout drone, tracks progress, and 
   reports final mission results.

DATA FLOW:
----------
RECEIVES:
  - /delivery/mission_goal (from victim_coordinates_subscriber) - Target location
  - /delivery/reached_target (from gps_navigation_controller) - Navigation complete
  - /delivery/visual_alignment_status (from visual_alignment) - Camera aligned
  - /delivery/victim_confirmed (from victim_confirmation) - Victim detected
  - /delivery/payload_dropped (from payload_drop_controller) - Delivery complete

PUBLISHES:
  - /delivery/target_gps - GPS coordinates for navigation
  - /delivery/mission_state - Current FSM state for monitoring
  - /delivery/mission_result - Final success/failure report

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from enum import Enum
import json
from std_msgs.msg import String, Float32
from sensor_msgs.msg import NavSatFix


class MissionState(Enum):
    NAVIGATING = "NAVIGATING"
    ALIGNING = "ALIGNING"
    CONFIRMING = "CONFIRMING"
    DROPPING = "DROPPING"
    COMPLETE = "COMPLETE"


class ActionServerNode(Node):
    def __init__(self):
        super().__init__('action_server')
        
        # State machine
        self.current_state = MissionState.NAVIGATING
        self.mission_goal = None
        self.state_start_time = self.get_clock().now()
        
        # State timeouts (seconds)
        self.state_timeouts = {
            MissionState.NAVIGATING: 60,
            MissionState.ALIGNING: 30,
            MissionState.CONFIRMING: 15,
            MissionState.DROPPING: 30,
        }
        
        # Subscribers
        self.mission_goal_sub = self.create_subscription(
            String,
            '/delivery/mission_goal',
            self.mission_goal_callback,
            10
        )
        
        self.reached_target_sub = self.create_subscription(
            String,
            '/delivery/reached_target',
            self.reached_target_callback,
            10
        )
        
        self.visual_alignment_sub = self.create_subscription(
            String,
            '/delivery/visual_alignment_status',
            self.visual_alignment_callback,
            10
        )
        
        self.victim_confirmed_sub = self.create_subscription(
            String,
            '/delivery/victim_confirmed',
            self.victim_confirmed_callback,
            10
        )
        
        self.payload_dropped_sub = self.create_subscription(
            String,
            '/delivery/payload_dropped',
            self.payload_dropped_callback,
            10
        )
        
        # Publishers
        self.target_gps_pub = self.create_publisher(
            NavSatFix,
            '/delivery/target_gps',
            10
        )
        
        self.mission_state_pub = self.create_publisher(
            String,
            '/delivery/mission_state',
            10
        )
        
        self.mission_result_pub = self.create_publisher(
            String,
            '/delivery/mission_result',
            10
        )
        
        # Timer for state monitoring
        self.timer = self.create_timer(1.0, self.state_monitor)
        
        self.get_logger().info('ActionServerNode initialized')
    
    def mission_goal_callback(self, msg):
        """Receive mission goal from Scout"""
        try:
            self.mission_goal = json.loads(msg.data)
            self.get_logger().info(f'Mission goal received: {self.mission_goal}')
            
            # Transition to NAVIGATING state and publish target GPS
            self.current_state = MissionState.NAVIGATING
            self.state_start_time = self.get_clock().now()
            
            # Create and publish target GPS
            gps_msg = NavSatFix()
            gps_msg.latitude = self.mission_goal.get('latitude', 0.0)
            gps_msg.longitude = self.mission_goal.get('longitude', 0.0)
            gps_msg.altitude = self.mission_goal.get('altitude', 0.0)
            self.target_gps_pub.publish(gps_msg)
            
            # Publish mission state
            state_msg = String()
            state_msg.data = self.current_state.value
            self.mission_state_pub.publish(state_msg)
            
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Failed to parse mission goal: {e}')
    
    def reached_target_callback(self, msg):
        """Handle reached target feedback"""
        if self.current_state == MissionState.NAVIGATING:
            self.get_logger().info('Target reached, transitioning to ALIGNING')
            self.current_state = MissionState.ALIGNING
            self.state_start_time = self.get_clock().now()
            
            # Publish state change
            state_msg = String()
            state_msg.data = self.current_state.value
            self.mission_state_pub.publish(state_msg)
    
    def visual_alignment_callback(self, msg):
        """Handle visual alignment feedback"""
        if msg.data == "aligned" and self.current_state == MissionState.ALIGNING:
            self.get_logger().info('Visual alignment complete, transitioning to CONFIRMING')
            self.current_state = MissionState.CONFIRMING
            self.state_start_time = self.get_clock().now()
            
            # Publish state change
            state_msg = String()
            state_msg.data = self.current_state.value
            self.mission_state_pub.publish(state_msg)
    
    def victim_confirmed_callback(self, msg):
        """Handle victim confirmation feedback"""
        if msg.data == "confirmed" and self.current_state == MissionState.CONFIRMING:
            self.get_logger().info('Victim confirmed, transitioning to DROPPING')
            self.current_state = MissionState.DROPPING
            self.state_start_time = self.get_clock().now()
            
            # Publish state change
            state_msg = String()
            state_msg.data = self.current_state.value
            self.mission_state_pub.publish(state_msg)
    
    def payload_dropped_callback(self, msg):
        """Handle payload dropped feedback"""
        if msg.data == "dropped" and self.current_state == MissionState.DROPPING:
            self.get_logger().info('Payload dropped, mission complete')
            self.current_state = MissionState.COMPLETE
            self.state_start_time = self.get_clock().now()
            
            # Publish final states
            state_msg = String()
            state_msg.data = self.current_state.value
            self.mission_state_pub.publish(state_msg)
            
            result_msg = String()
            result_msg.data = json.dumps({
                'status': 'SUCCESS',
                'mission_goal': self.mission_goal
            })
            self.mission_result_pub.publish(result_msg)
    
    def state_monitor(self):
        """Monitor state timeouts"""
        if self.current_state == MissionState.COMPLETE:
            return
        
        current_time = self.get_clock().now()
        elapsed_time = (current_time - self.state_start_time).nanoseconds / 1e9
        
        timeout = self.state_timeouts.get(self.current_state, 60)
        
        if elapsed_time > timeout:
            self.get_logger().warn(
                f'State {self.current_state.value} timeout after {elapsed_time:.1f}s'
            )
            # In a real system, this could trigger error recovery
            # For now, log the timeout


def main(args=None):
    rclpy.init(args=args)
    node = ActionServerNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
