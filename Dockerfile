# Use the specified ROS 2 Humble desktop image as the base
FROM osrf/ros:humble-desktop

# Replace /bin/sh with /bin/bash
RUN rm /bin/sh && ln -s /bin/bash /bin/sh

# Add the Ignition Gazebo repository and install ignition-gazebo6
RUN apt-get update && apt-get install -y \
    wget \
    lsb-release \
    gnupg
RUN sh -c 'echo "deb http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -sc) main" > /etc/apt/sources.list.d/gazebo-stable.list'
RUN wget https://packages.osrfoundation.org/gazebo.key -O - | apt-key add -
RUN apt-get update && apt-get install -y libignition-gazebo6 libignition-gazebo6-dev


# Install dependencies with apt
RUN apt-get update && apt-get install -y \
    ament-cmake \
    python3-pip \
    python3-colcon-common-extensions \
    python3-vcstool \
    ros-humble-joint-state-publisher-gui \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-kortex-bringup \
    ros-humble-ros2-control \
    ros-humble-ros2-controllers \
    ros-humble-moveit \
    ros-humble-xacro \
    ros-humble-ros-gz-bridge \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-gazebo-ros2-control \
    ros-humble-rviz2 \
    software-properties-common \
    libignition-transport11-dev \
    libgflags-dev \
    ros-humble-kinematics-interface-kdl \
    ros-humble-kinova-gen3-7dof-robotiq-2f-85-moveit-config \
 && rm -rf /var/lib/apt/lists/*

# Fix missing update
RUN apt-get update --fix-missing

# Copy the entire colcon_ws directory with the submodule into the Docker image
COPY colcon_ws/ /colcon_ws/

# Install module dependencies for colcon_ws
WORKDIR /colcon_ws/
RUN rosdep update
RUN rosdep install --from-paths src --ignore-src -r -y

# Import additional repositories using vcs
RUN vcs import src --skip-existing --input src/ros2_kortex/ros2_kortex.humble.repos
RUN vcs import src --skip-existing --input src/ros2_kortex/ros2_kortex-not-released.humble.repos
RUN vcs import src --skip-existing --input src/ros2_kortex/simulation.humble.repos

# Build the colcon_ws
WORKDIR /colcon_ws/src/picknik_controllers/
RUN git checkout humble
WORKDIR /colcon_ws/
RUN source /opt/ros/humble/setup.bash && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release --parallel-workers 3 --symlink-install

# Copy overlay_ws to docker image
COPY overlay_ws/src/ /overlay_ws/src/

# Install module dependencies of overlay_ws
WORKDIR /overlay_ws/
RUN apt-get update && rosdep update
RUN rosdep install --from-paths src --ignore-src -r -y 

# Source and build overlay_ws
RUN source /colcon_ws/install/setup.bash && colcon build --symlink-install

# Add overlay ws source to bashrc
RUN echo "source /overlay_ws/install/setup.bash" >> ~/.bashrc

# Copy entrypoint scripts and make them executable
COPY entrypoint_scripts/ /entrypoint_scripts/
RUN chmod +x /entrypoint_scripts/*.sh

# Copy custom rviz config
COPY /overlay_ws/src/moveit.rviz /colcon_ws/src/ros2_kortex/kortex_moveit_config/kinova_gen3_7dof_robotiq_2f_85_moveit_config/config/
