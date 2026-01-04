from setuptools import find_packages, setup

package_name = 'delivery_drone_system'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/delivery_config.yaml']),
        ('share/' + package_name + '/launch', ['launch/delivery_system.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='kaveri',
    maintainer_email='kaveribollineni20004@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'action_server=delivery_drone_system.action_server_node:main',
            'system_supervisor=delivery_drone_system.system_supervisor_node:main',
            'victim_coordinates_subscriber=delivery_drone_system.victim_coordinates_subscriber_node:main',
            'gps_navigation_controller=delivery_drone_system.gps_navigation_controller_node:main',
            'visual_alignment=delivery_drone_system.visual_alignment_node:main',
            'victim_confirmation=delivery_drone_system.victim_confirmation_node:main',
            'payload_drop_controller=delivery_drone_system.payload_drop_controller_node:main',
            'drone_interface=delivery_drone_system.drone_interface_node:main',
            'telemetry_monitor=delivery_drone_system.telemetry_monitor_node:main',
        ],
    },
)
