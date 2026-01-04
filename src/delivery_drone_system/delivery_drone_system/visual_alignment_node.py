"""
VISUAL ALIGNMENT NODE - Camera-Based Precision Positioning
===========================================================

PURPOSE:
--------
This node performs FINE-GRAINED ALIGNMENT using the drone's camera to
center the victim in the frame before payload drop.

WHY IT'S NEEDED:
----------------
1. GPS LIMITATIONS: GPS accuracy is typically 2-5 meters. For precise
   payload delivery, we need sub-meter accuracy using visual feedback.

2. CAMERA CENTERING: Uses computer vision to detect the victim and
   adjust drone position until victim is centered in camera frame.

3. DROP ACCURACY: If payload is dropped without alignment, it could
   land meters away from the victim - potentially useless in emergencies.

4. VISUAL SERVOING: This is a classic robotics technique where camera
   feedback drives motion control for precision tasks.

DATA FLOW:
----------
RECEIVES:
  - /delivery/reached_target (String) - Trigger to start alignment

PUBLISHES:
  - /delivery/visual_alignment_status (String):
    - "aligning" - Still centering the victim
    - "aligned" - Victim is centered, ready for next phase

ALIGNMENT PROCESS (Simulated):
  1. Receive "reached" signal from GPS navigation
  2. Start alignment timer (0.3s intervals)
  3. Increment progress by 20% each cycle
  4. After ~1.5 seconds, alignment complete
  5. Publish "aligned" status

REAL-WORLD IMPLEMENTATION:
  In production, this would:
  - Capture camera frames
  - Run object detection (find victim bounding box)
  - Calculate offset from frame center
  - Send velocity commands to center the target
  - Use PID controller for smooth convergence

RELATED CONCEPTS:
  - Visual servoing
  - Image-based control
  - Precision landing

AUTHOR: Delivery Drone System
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class VisualAlignmentNode(Node):
    def __init__(self):
        super().__init__('visual_alignment')
        
        # Alignment state
        self.target_reached = False
        self.alignment_progress = 0.0  # 0 to 1
        self.alignment_published = False
        
        # Subscriber for target reached trigger
        self.reached_target_sub = self.create_subscription(
            String,
            '/delivery/reached_target',
            self.reached_target_callback,
            10
        )
        
        # Publisher
        self.alignment_status_pub = self.create_publisher(
            String,
            '/delivery/visual_alignment_status',
            10
        )
        
        # Timer for simulated camera alignment
        self.alignment_timer = self.create_timer(0.3, self.simulate_alignment)
        
        self.get_logger().info('VisualAlignmentNode initialized')
    
    def reached_target_callback(self, msg):
        """Handle target reached signal"""
        if msg.data == "reached":
            self.get_logger().info('Target reached, starting visual alignment')
            self.target_reached = True
            self.alignment_progress = 0.0
            self.alignment_published = False
    
    def simulate_alignment(self):
        """Simulate visual alignment process"""
        if not self.target_reached or self.alignment_published:
            return
        
        # Simulate gradual alignment
        self.alignment_progress += 0.2  # 20% progress per 0.3 seconds
        self.alignment_progress = min(self.alignment_progress, 1.0)
        
        self.get_logger().debug(f'Alignment progress: {self.alignment_progress * 100:.1f}%')
        
        # Publish status
        status_msg = String()
        
        if self.alignment_progress >= 1.0:
            status_msg.data = "aligned"
            self.alignment_published = True
            self.get_logger().info('Visual alignment complete')
        else:
            status_msg.data = "aligning"
        
        self.alignment_status_pub.publish(status_msg)


def main(args=None):
    rclpy.init(args=args)
    node = VisualAlignmentNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
