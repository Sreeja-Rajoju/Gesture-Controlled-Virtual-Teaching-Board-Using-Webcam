import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import time
import os
import urllib.request
import datetime
import math
import threading
import queue

# Try importing Speech Recognition (Graceful degradation if missing)
try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("Warning: 'speech_recognition' module not found. Voice commands disabled.")
    print("Run: pip install SpeechRecognition pyaudio")

class VirtualGestureBoardPro:
    def __init__(self):
        # --- Initialization ---
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 1280)  # Width
        self.cap.set(4, 720)   # Height
        self.width = 1280
        self.height = 720

        # --- Assets ---
        self.model_path = 'hand_landmarker.task'
        if not os.path.exists(self.model_path):
            print("Downloading hand_landmarker.task model...")
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
            urllib.request.urlretrieve(url, self.model_path)
            print("Download complete.")

        # --- MediaPipe Setup ---
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=self.print_result)
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.latest_result = None
        self.timestamp_ms = 0

        # --- Theme & Colors (Pro Dark Mode) ---
        self.colors = {
            "BG_MAIN": (30, 30, 30),      # Dark Slate
            "SIDEBAR": (50, 50, 50),      # Lighter Slate
            "ACCENT": (255, 165, 0),      # Orange Accent
            "TEXT": (220, 220, 220),      # Off-White
            
            "CYAN": (255, 255, 0),
            "MAGENTA": (255, 0, 255),
            "LIME": (0, 255, 0),
            "RED": (0, 0, 255),
            "ORANGE": (0, 165, 255),
            "PURPLE": (255, 0, 128),
            "WHITE": (255, 255, 255),
            "ERASER": (0, 0, 0)
        }
        
        # Determine current draw color
        self.current_color_name = "CYAN"
        self.draw_color = self.colors["CYAN"]
        self.brush_thickness = 10
        self.eraser_thickness = 60
        
        # --- State Variables ---
        self.xp, self.yp = 0, 0
        
        # Navigation (Pan & Zoom)
        self.offset_x = 0
        self.offset_y = 0
        self.zoom_level = 1.0
        self.zoom_start_dist = None
        self.zoom_start_level = 1.0
        
        self.right_hand_pinch_start = None
        self.right_hand_start_offset = None

        # Drawing Modes
        self.draw_mode = "FREEHAND" # CUBE, PYRAMI, CYLIN, CONE
        self.shape_start_canvas = None # (cx, cy) in CANVAS coordinates
        self.current_tool = "FREEHAND" # For UI Highlighting

        # Canvas
        # We make a larger virtual canvas to handle zoom/pan effectively
        # But for simplicity, we map coordinates dynamically on a same-size buffer
        # and just shift/scale user inputs.
        self.img_canvas = np.zeros((720, 1280, 3), np.uint8)

        # --- UI Layout ---
        self.sidebar_width = 100
        self.bottom_bar_height = 80
        
        self.tools = [
            {"name": "FREEHAND", "icon": "Pen", "rect": (10, 80, 80, 60)},
            {"name": "CUBE", "icon": "Cube", "rect": (10, 150, 80, 60)},
            {"name": "CYLINDER", "icon": "Cyl", "rect": (10, 220, 80, 60)},
            {"name": "PYRAMID", "icon": "Pyr", "rect": (10, 290, 80, 60)},
            {"name": "CONE", "icon": "Cone", "rect": (10, 360, 80, 60)},
            {"name": "SAVE", "icon": "Save", "rect": (10, 500, 80, 60)},
            {"name": "CLEAR", "icon": "Clear", "rect": (10, 570, 80, 60)},
        ]
        
        self.color_btns = []
        c_names = ["CYAN", "MAGENTA", "LIME", "RED", "ORANGE", "PURPLE", "WHITE"]
        spacing = 80
        start_x = 150
        for i, name in enumerate(c_names):
            self.color_btns.append({
                "name": name,
                "color": self.colors[name],
                "center": (start_x + i*spacing, 680),
                "radius": 25
            })

        # --- Voice Command Setup ---
        self.voice_queue = queue.Queue()
        if VOICE_AVAILABLE:
            self.start_voice_thread()

    def start_voice_thread(self):
        def listen():
            recognizer = sr.Recognizer()
            mic = sr.Microphone()
            with mic as source:
                recognizer.adjust_for_ambient_noise(source)
                while True:
                    try:
                        audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)
                        text = recognizer.recognize_google(audio).lower()
                        print(f"Voice: {text}")
                        
                        if "clear" in text: self.voice_queue.put("CLEAR")
                        elif "save" in text: self.voice_queue.put("SAVE")
                        elif "red" in text: self.voice_queue.put("RED")
                        elif "blue" in text or "cyan" in text: self.voice_queue.put("CYAN")
                        elif "green" in text or "lime" in text: self.voice_queue.put("LIME")
                        elif "purple" in text: self.voice_queue.put("PURPLE")
                        elif "white" in text: self.voice_queue.put("WHITE")
                        elif "cube" in text: self.voice_queue.put("CUBE")
                        
                    except sr.WaitTimeoutError: pass
                    except sr.UnknownValueError: pass
                    except Exception as e: print(e)
        
        t = threading.Thread(target=listen, daemon=True)
        t.start()
        print("Voice Listening Started...")

    def print_result(self, result, output_image, timestamp_ms):
        self.latest_result = result

    # --- Coordinate Transformations ---
    def get_transform_offsets(self):
        center_x = self.width / 2
        center_y = self.height / 2
        tx = (1 - self.zoom_level) * center_x + self.offset_x
        ty = (1 - self.zoom_level) * center_y + self.offset_y
        return tx, ty

    def screen_to_canvas(self, sx, sy):
        # Canvas = (Screen - Tv) / Zoom
        tx, ty = self.get_transform_offsets()
        cx = (sx - tx) / self.zoom_level
        cy = (sy - ty) / self.zoom_level
        return int(cx), int(cy)

    def canvas_to_screen(self, cx, cy):
        # Screen = (Canvas * Zoom) + Tv
        tx, ty = self.get_transform_offsets()
        sx = (cx * self.zoom_level) + tx
        sy = (cy * self.zoom_level) + ty
        return int(sx), int(sy)

    # --- Drawing Helpers ---
    def draw_grid_background(self, img):
        # We need to draw a grid that moves with Pan and Zoom
        grid_size = 50 * self.zoom_level
        
        # Start positions based on offset modulo grid size to create infinite effect
        start_x = int(self.offset_x % grid_size)
        start_y = int(self.offset_y % grid_size)
        
        for x in range(start_x, self.width, int(grid_size)):
            cv2.line(img, (x, 0), (x, self.height), (60, 60, 60), 1)
        
        for y in range(start_y, self.height, int(grid_size)):
            cv2.line(img, (0, y), (self.width, y), (60, 60, 60), 1)

    def draw_ui(self, img):
        # Sidebar
        cv2.rectangle(img, (0, 0), (self.sidebar_width, self.height), self.colors["SIDEBAR"], -1)
        cv2.line(img, (self.sidebar_width, 0), (self.sidebar_width, self.height), (100,100,100), 2)
        
        # Tools
        for tool in self.tools:
            x, y, w, h = tool["rect"]
            color = (80, 80, 80)
            if self.current_tool == tool["name"]:
                color = self.colors["ACCENT"] # Orange Highlight
            
            cv2.rectangle(img, (x, y), (x+w, y+h), color, -1)
            cv2.rectangle(img, (x, y), (x+w, y+h), (200,200,200), 1)
            
            # Label
            label = tool["icon"]
            cv2.putText(img, label, (x+5, y+35), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.colors["TEXT"], 1)

        # Bottom Color Bar
        cv2.rectangle(img, (self.sidebar_width, self.height - self.bottom_bar_height), (self.width, self.height), self.colors["SIDEBAR"], -1)
        cv2.line(img, (self.sidebar_width, self.height - self.bottom_bar_height), (self.width, self.height - self.bottom_bar_height), (100,100,100), 2)
        
        for btn in self.color_btns:
            cx, cy = btn["center"]
            # Highlight if selected
            if self.current_color_name == btn["name"]:
                cv2.circle(img, (cx, cy), btn["radius"]+4, (255,255,255), 2)
            
            cv2.circle(img, (cx, cy), btn["radius"], btn["color"], -1)

        # Status Bar Info
        voice_status = "Listn" if VOICE_AVAILABLE else "Off"
        info = f"Zoom: {self.zoom_level:.1f}x | Mode: {self.draw_mode} | Mic: {voice_status}"
        cv2.putText(img, info, (self.width - 350, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    def draw_wireframe_shape(self, canvas, shape_type, p1, p2, color, thickness):
        # p1, p2 are in CANVAS Coordinates
        x1, y1 = p1
        x2, y2 = p2
        w = int(np.hypot(x2-x1, y2-y1))
        if w == 0: w = 1
        
        if shape_type == "CUBE":
            cv2.rectangle(canvas, (x1, y1), (x2, y1+w), color, thickness)
            offset = int(w * 0.3)
            cv2.rectangle(canvas, (x1+offset, y1-offset), (x2+offset, y1+w-offset), color, thickness)
            cv2.line(canvas, (x1,y1), (x1+offset, y1-offset), color, thickness)
            cv2.line(canvas, (x2,y1), (x2+offset, y1-offset), color, thickness)
            cv2.line(canvas, (x1,y1+w), (x1+offset, y1+w-offset), color, thickness)
            cv2.line(canvas, (x2,y1+w), (x2+offset, y1+w-offset), color, thickness)
            
        elif shape_type == "CYLINDER":
            cv2.ellipse(canvas, (x1, y1), (int(w/2), int(w/6)), 0, 0, 360, color, thickness)
            top_y = y1 - w
            cv2.ellipse(canvas, (x1, top_y), (int(w/2), int(w/6)), 0, 0, 360, color, thickness)
            cv2.line(canvas, (x1-int(w/2), y1), (x1-int(w/2), top_y), color, thickness)
            cv2.line(canvas, (x1+int(w/2), y1), (x1+int(w/2), top_y), color, thickness)
            
        elif shape_type == "PYRAMID":
            # Simple pyramid (Square base projection)
            cx = (x1 + x2) // 2
            top_y = y1 - w
            cv2.line(canvas, (x1, y1), (x2, y1), color, thickness) # Base front
            cv2.line(canvas, (x1, y1), (cx, top_y), color, thickness)
            cv2.line(canvas, (x2, y1), (cx, top_y), color, thickness)
            # 3D hint
            cv2.line(canvas, (x1 + w//3, y1 - w//3), (cx, top_y), color, thickness)
            cv2.line(canvas, (x1, y1), (x1 + w//3, y1 - w//3), color, thickness)
            cv2.line(canvas, (x2, y1), (x1 + w//3, y1 - w//3), color, thickness)

        elif shape_type == "CONE":
             cv2.ellipse(canvas, (x1, y1), (int(w/2), int(w/6)), 0, 0, 360, color, thickness)
             top_y = y1 - w
             cv2.line(canvas, (x1-int(w/2), y1), (x1, top_y), color, thickness)
             cv2.line(canvas, (x1+int(w/2), y1), (x1, top_y), color, thickness)

    def get_fingers_up(self, lm_list):
        fingers = []
        tip_ids = [4, 8, 12, 16, 20]
        # Thumb
        if lm_list[tip_ids[0]][0] > lm_list[tip_ids[0] - 1][0]: fingers.append(1)
        else: fingers.append(0)
        # Filters
        for id in range(1, 5):
            if lm_list[tip_ids[id]][1] < lm_list[tip_ids[id] - 2][1]: fingers.append(1)
            else: fingers.append(0)
        return fingers

    def run(self):
        p_time = 0
        save_msg_timer = 0
        
        while True:
            # 1. Process Voice Queue
            try:
                while not self.voice_queue.empty():
                    cmd = self.voice_queue.get_nowait()
                    if cmd == "CLEAR": self.img_canvas = np.zeros((720, 1280, 3), np.uint8)
                    elif cmd == "SAVE": 
                        cv2.imwrite(f"voice_save_{int(time.time())}.png", self.img_canvas)
                        save_msg_timer = 60
                    elif cmd in self.colors:
                        self.current_color_name = cmd
                        self.draw_color = self.colors[cmd]
                        self.draw_mode = "FREEHAND"
                        self.current_tool = "FREEHAND"
            except: pass

            success, img = self.cap.read()
            if not success: break
            img = cv2.flip(img, 1)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
            
            self.timestamp_ms += int(1000/30)
            self.landmarker.detect_async(mp_image, int(time.time() * 1000))

            # --- RENDER BACKGROUND ---
            # Fill background with Dark theme
            bg = np.zeros_like(img)
            bg[:] = self.colors["BG_MAIN"]
            self.draw_grid_background(bg)
            
            # Combine Drawings with Background
            # Apply Zoom/Pan to Canvas:
            # Transform: Scale around Center (width/2, height/2) then Translate
            
            # 1. Translate Center to Origin
            # 2. Scale
            # 3. Translate Origin back to Center
            # 4. Apply Pan Offsets
            
            center_x = self.width / 2
            center_y = self.height / 2
            
            # M = [ [z, 0, (1-z)*cx + offx], [0, z, (1-z)*cy + offy] ]
            tx = (1 - self.zoom_level) * center_x + self.offset_x
            ty = (1 - self.zoom_level) * center_y + self.offset_y
            
            M = np.float32([
                [self.zoom_level, 0, tx],
                [0, self.zoom_level, ty]
            ])
            
            # Viewport of canvas
            canvas_view = cv2.warpAffine(self.img_canvas, M, (self.width, self.height))
            
            # Merge (Simple addition since background is dark)
            # Create mask of drawings
            img_gray = cv2.cvtColor(canvas_view, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(img_gray, 10, 255, cv2.THRESH_BINARY)
            mask_inv = cv2.bitwise_not(mask)
            
            # Black-out area of drawings in BG
            bg_bg = cv2.bitwise_and(bg, bg, mask=mask_inv)
            # Take only drawings
            fg = cv2.bitwise_and(canvas_view, canvas_view, mask=mask)
            
            # Combine
            final_view = cv2.add(bg_bg, fg)
            
            # Draw UI
            self.draw_ui(final_view)

            # --- HAND LOGIC ---
            if self.latest_result and self.latest_result.hand_landmarks:
                
                # Check for 2-Hand Zoom gesture first
                if len(self.latest_result.hand_landmarks) == 2:
                    h1 = self.latest_result.hand_landmarks[0]
                    h2 = self.latest_result.hand_landmarks[1]
                    
                    # Check pinch on both hands
                    # Simple check: Distance between Thumb and Index
                    p1_idx = (int(h1[8].x * self.width), int(h1[8].y * self.height)) 
                    p1_th = (int(h1[4].x * self.width), int(h1[4].y * self.height))
                    p2_idx = (int(h2[8].x * self.width), int(h2[8].y * self.height))
                    p2_th = (int(h2[4].x * self.width), int(h2[4].y * self.height))
                    
                    dist1 = np.hypot(p1_idx[0]-p1_th[0], p1_idx[1]-p1_th[1])
                    dist2 = np.hypot(p2_idx[0]-p2_th[0], p2_idx[1]-p2_th[1])
                    
                    if dist1 < 40 and dist2 < 40:
                        # ZOOM GESTURE ACTIVE
                        # Calculate center of zoom (midpoint of two hands)
                        cx = (p1_idx[0] + p2_idx[0]) // 2
                        cy = (p1_idx[1] + p2_idx[1]) // 2
                        
                        # Calculate spread distance
                        spread = np.hypot(p1_idx[0]-p2_idx[0], p1_idx[1]-p2_idx[1])
                        
                        if self.zoom_start_dist is None:
                            self.zoom_start_dist = spread
                            self.zoom_start_level = self.zoom_level
                        else:
                            # Ratio
                            scale = spread / self.zoom_start_dist
                            target_zoom = self.zoom_start_level * scale
                            
                            # Clamp zoom
                            self.zoom_level = max(0.5, min(target_zoom, 3.0))
                            
                        cv2.putText(final_view, f"ZOOMING: {self.zoom_level:.2f}x", (cx-50, cy-50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
                        
                        # Skip other process
                        # Show hands
                        # ...
                    else:
                        self.zoom_start_dist = None

                # Process Individual Hands
                handedness_list = [h[0].category_name for h in self.latest_result.handedness]
                
                for idx, hand_landmarks in enumerate(self.latest_result.hand_landmarks):
                    hand_label = handedness_list[idx] if idx < len(handedness_list) else "Unknown"
                    
                    lm_list = []
                    for lm in hand_landmarks:
                        lm_list.append((int(lm.x * self.width), int(lm.y * self.height)))
                    
                    x1, y1 = lm_list[8]  # Indx Tip
                    x2, y2 = lm_list[12] # Mid Tip
                    fingers = self.get_fingers_up(lm_list)
                    
                    # Cyber Hand Visual
                    for pt in lm_list: cv2.circle(final_view, pt, 3, (100,100,100), -1)

                    # --- RIGHT HAND (Navigation) ---
                    if hand_label == "Right":
                        # Pinch
                        length = np.hypot(x1 - lm_list[4][0], y1 - lm_list[4][1])
                        if length < 40:
                            if self.right_hand_pinch_start is None:
                                self.right_hand_pinch_start = (x1, y1)
                                self.right_hand_start_offset = (self.offset_x, self.offset_y)
                            else:
                                dx = x1 - self.right_hand_pinch_start[0]
                                dy = y1 - self.right_hand_pinch_start[1]
                                self.offset_x = self.right_hand_start_offset[0] + dx
                                self.offset_y = self.right_hand_start_offset[1] + dy
                        else:
                            self.right_hand_pinch_start = None

                    # --- LEFT HAND (Drawing) ---
                    elif hand_label == "Left":
                        # Convert screen coords to canvas coords
                        cx, cy = self.screen_to_canvas(x1, y1)
                        
                        # 1. Selection Mode (Index + Middle)
                        # Used for interacting with UI which is in SCREEN SPACE
                        if fingers[1] and fingers[2]:
                            self.xp, self.yp = 0, 0
                            self.shape_start_canvas = None
                            
                            # Cursor
                            cv2.circle(final_view, (x1, y1), 15, self.colors["ACCENT"], 2)
                            
                            # Check Hit Tests (UI is Screen Space)
                            # Sidebar
                            for tool in self.tools:
                                tx, ty, tw, th = tool["rect"]
                                if tx < x1 < tx+tw and ty < y1 < ty+th:
                                    if tool["name"] == "CLEAR": 
                                        self.img_canvas = np.zeros((720, 1280, 3), np.uint8)
                                    elif tool["name"] == "SAVE":
                                        cv2.imwrite(f"pro_save_{int(time.time())}.png", self.img_canvas)
                                        save_msg_timer = 60
                                    else:
                                        self.current_tool = tool["name"]
                                        self.draw_mode = tool["name"]

                            # Colors
                            for btn in self.color_btns:
                                bx, by = btn["center"]
                                if np.hypot(x1-bx, y1-by) < btn["radius"]:
                                    self.current_color_name = btn["name"]
                                    self.draw_color = btn["color"]
                                    # Reset to freehand usually?
                                    if self.draw_mode not in ["CUBE", "PYRAMID", "CYLINDER", "CONE"]:
                                        self.draw_mode = "FREEHAND" 
                                        self.current_tool = "FREEHAND"

                        # 2. Eraser Mode (Open Palm - >= 4 Fingers)
                        elif fingers.count(1) >= 4:
                            self.draw_mode = "FREEHAND"
                            self.draw_color = self.colors["ERASER"]
                            self.current_tool = "CLEAR" 
                            
                            # Rubbing Action Visual
                            cv2.circle(final_view, (x1, y1), 30, (200,200,200), 2)
                            cv2.putText(final_view, "ERASE", (x1-20, y1-40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

                            if self.xp == 0 and self.yp == 0:
                                self.xp, self.yp = cx, cy
                                
                            cv2.line(self.img_canvas, (self.xp, self.yp), (cx, cy), self.colors["ERASER"], self.eraser_thickness)
                            self.xp, self.yp = cx, cy

                        # 3. Draw Mode (Index Only)
                        elif fingers[1] and not fingers[2]:
                            # Valid Drawing Area - REMOVED RESTRICTION
                            
                            if self.draw_mode == "FREEHAND":
                                cv2.circle(final_view, (x1, y1), 8, self.draw_color, -1)
                                if self.xp == 0 and self.yp == 0:
                                    self.xp, self.yp = cx, cy
                                
                                cv2.line(self.img_canvas, (self.xp, self.yp), (cx, cy), self.draw_color, self.brush_thickness)
                                self.xp, self.yp = cx, cy
                            
                            else: # SHAPES
                                self.xp, self.yp = 0, 0
                                if self.shape_start_canvas is None:
                                    self.shape_start_canvas = (cx, cy)
                                
                                # Preview on Screen (Need to map start canvas -> screen)
                                sx_start, sy_start = self.canvas_to_screen(self.shape_start_canvas[0], self.shape_start_canvas[1])
                                
                                # Draw temp wireframe on Final View
                                self.draw_wireframe_shape(final_view, self.draw_mode, (sx_start, sy_start), (x1, y1), self.draw_color, 2)
                        
                        else:
                            # Released
                            if self.shape_start_canvas:
                                # Commit shape
                                self.draw_wireframe_shape(self.img_canvas, self.draw_mode, self.shape_start_canvas, (cx, cy), self.draw_color, 5)
                                self.shape_start_canvas = None
                            self.xp, self.yp = 0, 0

            # UI Overlays (Save Message)
            if save_msg_timer > 0:
                cv2.putText(final_view, "SAVED!", (500, 360), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 255, 0), 4)
                save_msg_timer -= 1
            
            # Show FPS
            fps = 1 / (time.time() - p_time) if (time.time() - p_time) > 0 else 0
            p_time = time.time()
            cv2.putText(final_view, f"FPS: {int(fps)}", (self.width - 120, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)

            cv2.imshow("Board Pro V3", final_view)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    board = VirtualGestureBoardPro()
    board.run()
