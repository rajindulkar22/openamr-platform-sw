import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    pkg = get_package_share_directory('openamrobot_nav2')
    map_file = os.path.join(pkg, 'maps', 'my_map.yaml')

    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg, 'launch', 'localization_launch.py')
        ),
        launch_arguments={
            'map': map_file,
            'use_sim_time': 'true',
        }.items(),
    )

    navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'true',
        }.items(),
    )

    rviz_config = os.path.join(pkg, 'rviz', 'nav2_view.rviz')

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        parameters=[{'use_sim_time': True}],
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            name='initial_pose_x',
            default_value='0.0',
            description='Initial robot X position in map frame'
        ),
        DeclareLaunchArgument(
            name='initial_pose_y',
            default_value='0.0',
            description='Initial robot Y position in map frame'
        ),
        DeclareLaunchArgument(
            name='initial_pose_yaw',
            default_value='0.0',
            description='Initial robot yaw in map frame'
        ),
        localization,
        navigation,
        rviz,
    ])
