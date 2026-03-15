# Project Documentation: Gesture-Controlled Virtual Teaching Board

## 1. Project Overview
The **Gesture-Controlled Virtual Teaching Board** is an advanced Human-Computer Interaction (HCI) application designed to transform a standard webcam into a touch-free digital canvas. Utilizing computer vision and machine learning, specifically **OpenCV** and **MediaPipe**, the system tracks hand movements in real-time, allowing users to draw, erase, and interact with a virtual interface using natural hand gestures.

## 2. Objectives
- To eliminate the need for physical hardware like whiteboards or touchscreen monitors in remote teaching environments.
- To provide a hygienic, touch-free interface for public kiosks or medical settings.
- To demonstrate the practical application of real-time computer vision in enhancing user productivity.

## 3. System Architecture
The system operates on a linear pipeline:
1.  **Input Acquisition**: Captures video frames from the webcam.
2.  **Preprocessing**: Flips the frame for a "mirror" effect and converts color spaces (BGR to RGB).
3.  **Hand Tracking (MediaPipe)**:
    - Detects 21 3D hand landmarks for **Two Hands** simultaneously.
    - Identifies "Left" vs "Right" handedness.
4.  **Gesture Recognition Logic**:
    - **Left Hand (Artist)**:
        - **Draw Mode**: Index Finger Extended.
        - **Select Mode**: Index + Middle Extended.
        - **Erase Mode**: Open Palm.
    - **Right Hand (Navigator)**:
        - **Pan Mode**: Pinch Gesture (Thumb + Index < 40px).
5.  **Graphics Rendering**:
    - **Shape Engine**: Calculates parametric points for 3D wireframes (Cube, Cone, etc.) based on drag distance.
    - **Matrix Translation**: Apply "Panning" offsets to the drawing canvas before rendering.
    - **UI Overlay**: Draws a Cybernetic/Glassmorphism interface.
6.  **Output Composition**: Merges the shifted canvas with the live video feed.

## 4. Technical Specifications
### Hardware Requirements
- **Webcam**: Standard USB or built-in laptop camera (720p recommended).
- **Processor**: Intel i5 / AMD Ryzen 5 or better (for smooth >30 FPS performance).

### Software Stack
- **Language**: Python 3.8+
- **Libraries**:
    - `opencv-python`: For image processing and UI drawing.
    - `mediapipe`: For robust hand tracking models.
    - `numpy`: For matrix operations and canvas management.

## 5. Key Features
- **Multi-Hand Intelligence**: Distinguishes between Left (Drawing) and Right (Panning) hands for bimanual workflow.
- **3D Wireframe Engine**: Gesture-based creation of geometric solids (Cube, Pyramid, Cylinder, Cone).
- **Glassmorphism UI**: A modern interface with expanded color palettes and icon-based tools.
- **Infinite Canvas**: Navigation gestures allow users to pan the board to find new drawing space.
- **Save & Share**: Integrated capture system to save the teaching session as high-res images.

## 6. User Manual
1.  **Launch**: Run `python virtual_board.py`.
2.  **Drawing (Left Hand)**: Raise Index Finger to draw. Open Palm to erase.
3.  **Tools**: Raise Two Fingers (Left Hand) to select **Colors** (Red, Cyan, Purple...) or **Shapes** (Cube, Cone...).
4.  **Navigation (Right Hand)**: Pinch your thumb and index finger. Drag your hand to move the board.
5.  **Saving**: Hover over the **Save Icon** to capture the screen.

## 7. Future Enhancements
- **Zoom Support**: Pinch to zoom in/out (currently only Pan is supported).
- **Voice Commands**: "Clear Board", "Select Red" via speech.
- **Professional Design**: Dark theme, grid layout, and sidebar tools (Planned).
