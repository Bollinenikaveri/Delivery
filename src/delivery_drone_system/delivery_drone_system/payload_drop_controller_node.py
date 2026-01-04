"""
PAYLOAD DROP CONTROLLER NODE - Servo-Actuated Delivery Mechanism
=================================================================

PURPOSE:
--------
This node controls the PHYSICAL PAYLOAD RELEASE MECHANISM - the servo
motor that opens the payload bay to drop supplies to the victim.

WHY IT'S NEEDED:
----------------
1. HARDWARE INTERFACE: The actual payload drop requires controlling a
   servo motor. This node manages that hardware interaction.

2. SAFETY INTERLOCK: Payload is ONLY dropped when BOTH conditions met:
   - Victim is confirmed (AI verification passed)
   - Camera is aligned (precision positioning complete)

3. SEQUENCE CONTROL: Drop mechanism requires specific timing:
   - Energize servo
   - Rotate to release angle
   - Hold for payload clearance
   - Return to closed position

4. FINAL MISSION STEP: This is the culmination of the entire delivery
   mission - the actual aid delivery to the victim.

DATA FLOW:
----------
RECEIVES:
  - /delivery/victim_confirmed (String) - "confirmed" from AI detection
  - /delivery/visual_alignment_status (String) - "aligned" from camera

PUBLISHES:
  - /delivery/payload_dropped (String) - "dropped" signals mission complete

DROP SEQUENCE (Simulated):
  1. Wait for both victim_confirmed AND aligned status
  2. Set drop_in_progress flag (prevents double-drops)
  3. Execute servo control sequence:
     - Send PWM signal to servo (e.g., 1500μs → 2000μs)
     - Wait for mechanism to open
     - Payload falls by gravity
  4. Publish "dropped" status
  5. Action server receives this and marks mission COMPLETE

SAFETY FEATURES:
  - Requires BOTH alignment AND confirmation (dual interlock)
  - Single-drop protection (payload_dropped flag)
  - Prevents re-triggering during active drop

REAL-WORLD HARDWARE:
  In production, this would interface with:
  - PWM controller (PCA9685 or similar)
  - Servo motor (e.g., MG996R)
  - GPIO pins on flight controller
  - Optional: Hall effect sensor for drop confirmation

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time


class PayloadDropControllerNode(Node):
    def __init__(self):
        super().__init__('payload_drop_controller')
        
        # Payload drop state
        self.victim_confirmed = False
        self.aligned = False
        self.drop_in_progress = False
        self.payload_dropped = False
        
        # Subscribers
        self.victim_confirmed_sub = self.create_subscription(
            String,
            '/delivery/victim_confirmed',
            self.victim_confirmed_callback,
            10
        )
        
        self.alignment_sub = self.create_subscription(
            String,
            '/delivery/visual_alignment_status',
            self.alignment_callback,
            10
        )
        
        # Publisher
        self.payload_dropped_pub = self.create_publisher(
            String,
            '/delivery/payload_dropped',
            10
        )
        
        # Timer for drop sequence
        self.drop_timer = self.create_timer(0.5, self.execute_drop_sequence)
        
        self.get_logger().info('PayloadDropControllerNode initialized')
    
    def victim_confirmed_callback(self, msg):
        """Handle victim confirmation"""
        if msg.data == "confirmed":
            self.victim_confirmed = True
            self.get_logger().info('Victim confirmed')
            self.check_drop_conditions()
    
    def alignment_callback(self, msg):
        """Handle alignment status"""
        if msg.data == "aligned":
            self.aligned = True
            self.get_logger().info('Visual alignment confirmed')
            self.check_drop_conditions()
    
    def check_drop_conditions(self):
        """Check if all conditions are met to drop payload"""
        if self.victim_confirmed and self.aligned and not self.drop_in_progress:
            self.drop_in_progress = True
            self.get_logger().info('All conditions met, initiating payload drop sequence')
    
    def execute_drop_sequence(self):
        """Execute servo control for payload drop"""
        if not self.drop_in_progress or self.payload_dropped:
            return
        
        # Simulate servo control sequence
        # In a real system, this would:
        # 1. Energize servo motor
        # 2. Rotate servo to release angle
        # 3. Verify release mechanism
        # 4. Return servo to rest position
        
        self.get_logger().debug('Executing payload drop sequence')
        
        # Simulate 0.5 second drop sequence per call
        # After first call, publish result
        payload_msg = String()
        payload_msg.data = "dropped"
        self.payload_dropped_pub.publish(payload_msg)
        
        self.payload_dropped = True
        self.drop_in_progress = False
        
        self.get_logger().info('Payload dropped successfully')


def main(args=None):
    rclpy.init(args=args)
    node = PayloadDropControllerNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
