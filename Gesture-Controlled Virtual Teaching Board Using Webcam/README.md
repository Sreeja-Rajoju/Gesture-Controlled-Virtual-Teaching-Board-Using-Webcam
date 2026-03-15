# Gesture-Controlled Virtual Teaching Board

A professional-grade computer vision application that turns your webcam into a virtual teaching board. Draw, erase, and interact using simple hand gestures.

## Features

- **Multi-Hand Interaction**:
  - **Left Hand**: Your primary **Drawing Hand**.
    - **Index Finger**: Draw / Create Shapes.
    - **Index + Middle**: Hover / Select Tools.
    - **Open Palm**: Erase.
  - **Right Hand**: Your **Navigation Hand**.
    - **Pinch (Thumb+Index)**: Pan/Move the canvas (Infinite Board).
- **Pro Tools**:
  - **3D Shapes**: Create Wireframe Cubes, Pyramids, Cylinders, and Cones.
  - **Save Work**: One-click save specific views as images.
- **Extended Palette**: Now with Red, Orange, Purple, White, etc.
- **Real-time Overlay**: Cybernetic hand visuals and neon aesthetics.

## Installation

1. **Prerequisites**: Ensure you have Python installed (3.7+ recommended).
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the script:
   ```bash
   python virtual_board.py
   ```
2. **Controls**:
   - **Left Hand**:
     - **Draw**: Index finger up.
     - **Select**: Index + Middle fingers up.
     - **Erase**: Open Palm.
   - **Right Hand**:
     - **Pan Board**: Pinch Thumb & Index finger and drag.
   - **Shapes**: Select a shape (Cube/Pyr/Cyl/Cone) -> Draw with Left Index -> Drag to size -> Release.
   - **Save**: Hover over "SAVE" button -> Image saved to folder.
   - **Clear**: Hover over "CLEAR" button.
   - **Quit**: Press 'q' on your keyboard to exit.

## Technologies Used
- **OpenCV**: Image processing and computer vision.
- **MediaPipe**: Real-time hand tracking.
- **NumPy**: Matrix operations for the drawing canvas.
