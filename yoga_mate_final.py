import cv2
import    mediapipe as mp
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from threading import Thread, Lock
import time         
import pyttsx3
import json
from PIL import Image, ImageTk
import os

# Initialize MediaPipe
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

# Voice engine with lock for thread safety
engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 0.9)
voice_lock = Lock()
last_voice_time = 0
VOICE_COOLDOWN = 4  # seconds between voice feedback

def speak(text):
    """Speak text using text-to-speech with cooldown"""
    def speak_thread():
        global last_voice_time
        current_time = time.time()

        with voice_lock:
            if current_time - last_voice_time >= VOICE_COOLDOWN:
                try:
                    engine.say(text)
                    engine.runAndWait()
                    last_voice_time = current_time
                except:
                    pass  # Silently fail if voice engine has issues

    Thread(target=speak_thread, daemon=True).start()

def calculate_angle(a, b, c):
    """Calculate angle between three points"""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)

    if angle > 180.0:
        angle = 360 - angle
    return angle

class YogaMateApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YogaMate 🧘 ")
        self.root.geometry("1200x700")
        self.root.configure(bg="#ffffff")

        # Load pose instructions
        self.load_pose_instructions()

        self.running = False
        self.correct_pose = False
        self.hold_start = None
        self.hold_time = 30
        self.current_pose = ""
        self.last_feedback_time = 0
        self.feedback_cooldown = 10  # seconds between repeated feedback
        self.pose_images = {}  # Cache for loaded images
        self.pose_correct_count = 0  # Counter for consecutive correct pose frames

        # ======= Breathing Exercise Variables (COMMENTED) =======
        # self.breathing_active = False
        # self.breathing_phase = 0  # 0: inhale, 1: hold, 2: exhale
        # self.breathing_size
        # self.breathing_direction = 1  # 1: growing, -1: shrinking

        self.setup_ui()

    def load_pose_instructions(self):
        """Load pose instructions from JSON file"""
        try:
            with open('pose_instructions.json', 'r') as f:
                self.pose_data = json.load(f)
        except FileNotFoundError:
            messagebox.showerror("Error", "Pose instructions file not found!")
            self.pose_data = {}

    def setup_ui(self):
        """Setup the enhanced user interface"""
        # ====== HEADER ======
        header = tk.Frame(self.root, bg="#ADA6D2", height=60, highlightbackground="#1F1A1A", highlightthickness=1)
        header.pack(fill="x")
        title = tk.Label( header, text="YogaMate 🧘", font=("Poppins", 26, "bold"),bg="#ADA6D2", fg="#1F1A1A" ) 
        title.pack(pady=12)


        # ====== MAIN CONTAINER ======
        container = tk.Frame(self.root, bg="#ffffff")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # LEFT SIDEBAR - Breathing Exercise, Yoga Dropdown & Timer
        sidebar_container = tk.Frame(container, bg="#f8f9fa", width=300)
        sidebar_container.pack(side="left", fill="y", padx=(0, 20))
        sidebar_container.pack_propagate(False)

        sidebar_canvas = tk.Canvas(sidebar_container, bg="#f8f9fa", width=300, highlightthickness=0)
        sidebar_canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(sidebar_container, orient="vertical", command=sidebar_canvas.yview)
        scrollbar.pack(side="right", fill="y")

        sidebar_canvas.configure(yscrollcommand=scrollbar.set)

        # Create the actual sidebar frame inside the canvas
        sidebar = tk.Frame(sidebar_canvas, bg="#f8f9fa", width=300)
        sidebar_id = sidebar_canvas.create_window((0,0), window=sidebar, anchor="nw")

        def on_sidebar_configure(event):
            sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all"))

        sidebar.bind("<Configure>", on_sidebar_configure)

        # ===== BREATHING EXERCISE SECTION (COMMENTED) =====
        # breathing_frame = tk.Frame(sidebar, bg="#0a3d62", bd=0, relief="flat")
        # breathing_frame.pack(fill="x", pady=(20,15), padx=10)
        #
        # self.breathing_canvas = tk.Canvas(
        #     breathing_frame,
        #     width=180,
        #     height=180,
        #     bg="#0a3d62",
        #     highlightthickness=0
        # )
        # self.breathing_canvas.pack(pady=0)
        #
        # self.breathing_circle = self.breathing_canvas.create_oval(
        #     60, 60, 120, 120,
        #     fill="#1e90ff", outline="#60a3bc", width=4
        # )
        #
        # self.breathing_status = self.breathing_canvas.create_text(
        #     90, 80, text="Ready", font=("Poppins", 20, "bold"), fill="#fff"
        # )
        # self.breathing_subtext = self.breathing_canvas.create_text(
        #     90, 110, text="Breathe and Relax", font=("Poppins", 12), fill="#dff9fb"
        # )
        #
        # self.breathing_timer_label = tk.Label(
        #     breathing_frame, text="", font=("Poppins", 18, "bold"),
        #     bg="#0a3d62", fg="#dff9fb"
        # )
        # self.breathing_timer_label.pack(pady=(8,0))
        #
        # self.breathing_btn = tk.Button(
        #     breathing_frame, text="Start →", font=("Poppins", 13, "bold"),
        #     bg="#00b894", fg="#fff", activebackground="#0984e3",
        #     relief="flat", width=12, bd=0, command=self.start_breathing,
        #     cursor="hand2", highlightthickness=0
        # )
        # self.breathing_btn.pack(pady=16)

        # ===== YOGA POSE SELECTION =====
        yoga_frame = tk.Frame(sidebar, bg="#f8f9fa")
        yoga_frame.pack(fill="x", pady=(15,10), padx=10)

        tk.Label(yoga_frame, text="🧘Select Yoga Pose", font=("Helvetica", 14, "bold"),
                bg="#f8f9fa").pack(anchor="w", pady=(0,10))

        # Dropdown
        self.pose_var = tk.StringVar()
        self.pose_dropdown = ttk.Combobox(yoga_frame, textvariable=self.pose_var,
                                         font=("Helvetica", 12), state="readonly")
    
        self.pose_dropdown["values"] = list(self.pose_data.keys())
        self.pose_dropdown.current(0)
        self.pose_dropdown.pack(fill="x", pady=(0,10))
        self.pose_dropdown.bind("<<ComboboxSelected>>", self.on_pose_select)

        # Add hover effect for dropdown
        def on_enter(event):
            self.pose_dropdown.config(style="Hover.TCombobox")

        def on_leave(event):
            self.pose_dropdown.config(style="TCombobox")

        self.pose_dropdown.bind("<Enter>", on_enter)
        self.pose_dropdown.bind("<Leave>", on_leave)

        # Configure hover style
        style = ttk.Style()
        style.configure("Hover.TCombobox", fieldbackground="#e0f7fa", bordercolor="#00bca0")

        # ===== TIMER SECTION =====
# ...existing code inside YogaMateApp.setup_ui()...
        # ===== TIMER SECTION (with selectable durations) =====
        timer_frame = tk.Frame(sidebar, bg="#f8f9fa")
        timer_frame.pack(fill="x", pady=(10,20), padx=10)

        tk.Label(timer_frame, text="⏱️ Timer", font=("Helvetica", 14, "bold"),
                 bg="#f8f9fa").pack(anchor="w", pady=(0,8))

        # Dropdown to choose duration
        tk.Label(timer_frame, text="Duration:", font=("Helvetica", 12),
                 bg="#f8f9fa").pack(anchor="w")
        self.timer_var = tk.StringVar()
        self.timer_dropdown = ttk.Combobox(
            timer_frame,
            textvariable=self.timer_var,
            values=["30s", "1 min", "3 min"],
            state="readonly",
            width=12,
            font=("Helvetica", 11)
        )
        # default to 30s
        self.timer_dropdown.current(0)
        self.timer_dropdown.pack(anchor="w", pady=(4,8))

        # Display of remaining time
        # Initialize hold_time mapping to match selection
        duration_map = {"30s": 30, "1 min": 60, "3 min": 180}
        sel = self.timer_var.get() if self.timer_var.get() else "30s"
        self.hold_time = duration_map.get(sel, 30)
        self.timer_label = tk.Label(timer_frame, text=f"{self.hold_time}s",
                                    font=("Helvetica", 28, "bold"),
                                    bg="#f8f9fa", fg="#2e86de")
        self.timer_label.pack(pady=5)
        self.timer_label.bind("<Button-1>", self.on_timer_label_click)

        # Bind selection change
        self.timer_dropdown.bind("<<ComboboxSelected>>", self.on_timer_select)

        # Yoga control buttons

        # Yoga control buttons
        yoga_btn_frame = tk.Frame(timer_frame, bg="#f8f9fa")
        yoga_btn_frame.pack(pady=10)

        # Create custom styles for buttons
        style = ttk.Style()
        style.configure("Rounded.TButton",
                       font=("Helvetica", 12, "bold"),
                       background="#00bca0",
                       foreground="black",
                       relief="flat",
                       borderwidth=0,
                       padding=(10, 5))
        style.map("Rounded.TButton",
                 background=[("active", "#009688")])

        style.configure("RoundedStop.TButton",
                       font=("Helvetica", 12),
                       background="#e60b0b",
                       foreground="black",
                       relief="flat",
                       borderwidth=0,
                       padding=(10, 5))
        style.map("RoundedStop.TButton",
                 background=[("active", "#cc0000")])

        self.start_btn = ttk.Button(yoga_btn_frame, text="Start Session", style="Rounded.TButton",
                                   command=self.start_session)
        self.start_btn.pack(side="left", padx=2)

        self.stop_btn = ttk.Button(yoga_btn_frame, text="Stop", style="RoundedStop.TButton",
                                  command=self.stop_session, state="disabled")
        self.stop_btn.pack(side="left", padx=2)

        # ===== POSE IMAGE DISPLAY (moved to bottom) =====
        self.image_frame = tk.Frame(sidebar, bg="#f8f9fa", height=180)
        self.image_frame.pack(fill="x", pady=(10,20), padx=10)
        self.image_frame.pack_propagate(False)

        self.pose_image_label = tk.Label(self.image_frame, text="📷 Pose Image",
                                       font=("Helvetica", 12), bg="#f8f9fa", fg="#666")
        self.pose_image_label.pack(expand=True)

        # ===== VIDEO PLACEHOLDER =====
        self.video_frame = tk.Frame(sidebar, bg="#f8f9fa", height=180)
        self.video_frame.pack(fill="x", pady=(0, 20), padx=10)
        self.video_frame.pack_propagate(False)

        self.video_label = tk.Label(
            self.video_frame,
            text="🎬 Video Placeholder",
            font=("Helvetica", 12, "italic"),
            bg="#f8f9fa",
            fg="#888"
        )
        self.video_label.pack(expand=True)

        # ====== RIGHT AREA - Camera & Instructions ======
        right_area = tk.Frame(container, bg="white", relief="groove", bd=2)
        right_area.pack(side="right", fill="both", expand=True)

        # Camera Feed (TOP RIGHT)
        self.camera_frame = tk.Frame(right_area, bg="black", height=400)
        self.camera_frame.pack(fill="x", pady=(20,10), padx=20)
        self.camera_frame.pack_propagate(False)

        self.camera_label = tk.Label(self.camera_frame, text="Camera Feed - Starting...",
                                   font=("Helvetica", 14), bg="black", fg="white")
        self.camera_label.pack(expand=True)

        # Instructions & Status (BOTTOM RIGHT)
        bottom_frame = tk.Frame(right_area, bg="white")
        bottom_frame.pack(fill="both", expand=True, padx=20, pady=(0,20))

        # Instructions
        instruction_frame = tk.Frame(bottom_frame, bg="white")
        instruction_frame.pack(fill="x", pady=(0,10))

        tk.Label(instruction_frame, text="Instructions:", font=("Helvetica", 14, "bold"),
                bg="white").pack(anchor="w")

        self.instruction_text = tk.Text(instruction_frame, height=6, wrap="word",
                                       font=("Helvetica", 11), bg="#f9f9f9", relief="flat")
        self.instruction_text.pack(fill="x", pady=5)

        # Status
        status_frame = tk.Frame(bottom_frame, bg="white")
        status_frame.pack(fill="x")

        tk.Label(status_frame, text="Status:", font=("Helvetica", 14, "bold"),bg="white").pack(anchor="w")

        self.status_text = tk.Text(status_frame, height=3, wrap="word",font=("Helvetica", 11), bg="#f9f9f9", relief="flat")
        self.status_text.pack(fill="x", pady=5)
        self.status_text.config(state="disabled")

        # Update initial display
        self.on_pose_select()

    def load_pose_image(self, pose_name):
        """Load and display pose image"""
        if pose_name in self.pose_data and "image" in self.pose_data[pose_name]:
            image_path = self.pose_data[pose_name]["image"]
            if os.path.exists(image_path):
                try:
                    img = Image.open(image_path).convert('RGB')
                    img = img.resize((250, 180), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.pose_image_label.config(image=photo, text="")
                    self.pose_image_label.image = photo  # Keep reference
                    return
                except Exception as e:
                    print(f"Error loading image: {e}")
    

        # Fallback to text
        self.pose_image_label.config(text=f"📷 {pose_name}\n(Image not found)", image="")

    def on_pose_select(self, event=None):
        """Update display when pose is selected"""
        pose = self.pose_var.get()
        if pose in self.pose_data:
            data = self.pose_data[pose]

            # Update instructions
            self.instruction_text.config(state="normal")
            self.instruction_text.delete(1.0, tk.END)
            self.instruction_text.insert(tk.END, f"🧘 {pose}\n\n")
            self.instruction_text.insert(tk.END, data["instructions"])
            self.instruction_text.config(state="disabled")

            # Load pose image
            self.load_pose_image(pose)

            # Clear status
            self.update_status("Select a pose and press Start Session")
    def on_timer_select(self, event=None):
        """Update hold_time when user selects a timer duration from the dropdown."""
        duration_map = {"30s": 30, "1 min": 60, "3 min": 180}
        sel = self.timer_var.get()
        self.hold_time = duration_map.get(sel, 30)
        self.timer_label.config(text=f"{self.hold_time}s")

    def on_timer_label_click(self, event=None):
        """Cycle through timer durations when timer label is clicked."""
        durations = ["30s", "1 min", "3 min"]
        current_index = durations.index(self.timer_var.get()) if self.timer_var.get() in durations else 0
        next_index = (current_index + 1) % len(durations)
        self.timer_var.set(durations[next_index])
        self.on_timer_select()
    def update_status(self, message):
        """Update status text"""
        self.status_text.config(state="normal")
        self.status_text.delete(1.0, tk.END)
        self.status_text.insert(tk.END, f"💬 {message}")
        self.status_text.config(state="disabled")

    def start_session(self):
        """Start the yoga session"""
        pose = self.pose_var.get()
        if not pose:
            messagebox.showwarning("Warning", "Please select a pose first!")
            return

        self.current_pose = pose
        self.running = True
        self.correct_pose = False
        self.hold_start = None
        self.last_feedback_time = 0

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.pose_dropdown.config(state="disabled")

        self.update_status(f"Starting {pose}... Get ready!")
        speak(f"Get ready for {pose}. Timer will start only when your pose is perfect.")

        # Start camera thread
        Thread(target=self.run_camera, daemon=True).start()

    def stop_session(self):
        """Stop the current session"""
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.pose_dropdown.config(state="readonly")
        self.timer_label.config(text="30s")
        self.update_status("Session stopped. Select a new pose to continue.")

    def run_camera(self):
        """Run camera and pose detection"""
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    break

                # Process frame
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(image)
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                if results.pose_landmarks:
                    # Draw landmarks
                    mp_drawing.draw_landmarks(
                        image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2),
                        mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2)
                    )

                    landmarks = results.pose_landmarks.landmark
                    pose_ok, feedback, wrong_pose = self.enhanced_pose_check(self.current_pose, landmarks)

                    if pose_ok:
                        self.pose_correct_count += 1
                        if self.pose_correct_count >= 10:  # Require 10 consecutive correct frames (~0.1 seconds)
                            if not self.correct_pose:
                                speak("Your pose is correct. Timer starting now.")
                                self.hold_start = time.time()
                                self.update_status("✅ Perfect pose! Hold for 30 seconds.")
                            self.correct_pose = True

                            # Update timer
                            elapsed = int(time.time() - self.hold_start)
                            remaining = max(0, self.hold_time - elapsed)
                            self.timer_label.config(text=f"{remaining}s")

                            if remaining <= 0:
                                speak("Excellent! You have held the pose perfectly.")
                                self.update_status("🎉 Pose completed perfectly! Great job!")
                                self.stop_session()
                                break
                    else:
                        self.pose_correct_count = 0  # Reset counter if pose is not correct
                        current_time = time.time()
                        # Only provide feedback if it's been a while since last feedback
                        if (current_time - self.last_feedback_time > self.feedback_cooldown):
                            if feedback:
                                speak(feedback)
                                self.update_status(f"❌ {feedback}")
                                self.last_feedback_time = current_time
                            elif wrong_pose:
                                speak(f"you are doing {wrong_pose}         . Please do {self.current_pose}.")
                                self.update_status(f"❌ Wrong pose detected: {wrong_pose}")
                                self.last_feedback_time = current_time

                        self.correct_pose = False
                        self.hold_start = None
                        self.timer_label.config(text="30s")

                # Convert to PIL Image for Tkinter
                img = Image.fromarray(image)
                img = img.resize((600, 400), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)

                # Update camera label
                self.camera_label.config(image=photo, text="")
                self.camera_label.image = photo

                # Small delay to prevent UI freezing
                time.sleep(0.01)

        cap.release()
        cv2.destroyAllWindows()
        self.stop_session()

    def enhanced_pose_check(self, pose_name, landmarks):
        """Enhanced pose checking with wrong pose detection"""
        if pose_name not in self.pose_data:
            return False, "Pose not recognized", None

        # Extract keypoints
        def lm(index):
            return [landmarks[index].x, landmarks[index].y]

        # Get all landmarks
        left_shoulder = lm(11)
        right_shoulder = lm(12)
        left_elbow = lm(13)
        right_elbow = lm(14)
        left_wrist = lm(15)
        right_wrist = lm(16)
        left_hip = lm(23)
        right_hip = lm(24)
        left_knee = lm(25)
        right_knee = lm(26)
        left_ankle = lm(27)
        right_ankle = lm(28)

        # Check for wrong poses first
        wrong_pose = self.detect_wrong_pose(landmarks)
        if wrong_pose and wrong_pose != pose_name:
            return False, f"You're doing {wrong_pose} instead of {pose_name}", wrong_pose

        # Relaxed pose-specific checking with Indian English feedback
        if pose_name == "Tree Pose":
            # Check if one foot is raised
            left_foot_height = left_ankle[1]
            right_foot_height = right_ankle[1]
            foot_height_diff = abs(left_foot_height - right_foot_height)

            if foot_height_diff < 0.08:  # Both feet on ground - relaxed threshold
                return False, "Please lift one foot and place it on the other thigh", None

            angle_hip = calculate_angle(left_knee, left_hip, right_hip)
            if 50 < angle_hip < 130:  # More relaxed range
                return True, None, None
            return False, "Lift your knee a bit higher and place foot on inner thigh", None

        elif pose_name == "Warrior II":
            front_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            back_leg_angle = calculate_angle(right_hip, right_knee, right_ankle)

            # More relaxed checking
            if 70 < front_knee_angle < 110 and back_leg_angle > 150:
                return True, None, None
            return False, "Bend your front knee to about 90 degrees and keep back leg straight", None

        elif pose_name == "Cobra Pose":
            # Check if person is lying on stomach with back arched
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            head_height = (left_shoulder[1] + right_shoulder[1]) / 2  # Approximate head position

            # Person should be lying down (hips and shoulders relatively close in height)
            if abs(hip_height - shoulder_height) < 0.2:  # Relaxed lying position
                # Back should be arched (shoulders higher than hips for backbend)
                if shoulder_height < hip_height - 0.05:  # Shoulders below hips indicates backbend
                    # Check if chest is lifted (head/shoulders above ground level)
                    if head_height < 0.7:  # Relaxed check for lifted chest
                        return True, None, None
                    return False, "Lift your chest higher off the ground", None
                return False, "Arch your back more while keeping hips on the ground", None
            return False, "Lie on your stomach with your hands under your shoulders", None

        elif pose_name == "Standing Prayer Pose":
            # Check if person is standing upright
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            hip_height = (left_hip[1] + right_hip[1]) / 2
            if shoulder_height < hip_height + 0.3:  # Standing posture (shoulders above hips) - relaxed
                # Check if hands are at chest level (between shoulders and hips)
                wrist_height = (left_wrist[1] + right_wrist[1]) / 2
                if wrist_height > shoulder_height - 0.2 and wrist_height < hip_height + 0.2:  # Relaxed range for chest level
                    # Check if hands are close together (palms touching)
                    wrist_distance = abs(left_wrist[0] - right_wrist[0])
                    if wrist_distance < 0.4:  # Hands close together - relaxed
                        # Check if elbows are bent (arms folded in prayer position)
                        left_elbow_angle = calculate_angle(left_shoulder, left_elbow, left_wrist)
                        right_elbow_angle = calculate_angle(right_shoulder, right_elbow, right_wrist)
                        if left_elbow_angle < 180 and right_elbow_angle < 180:  # Elbows bent - relaxed
                            return True, None, None
                        return False, "Bend your elbows and bring hands to heart center", None
                    return False, "Bring your palms closer together at your chest", None
                return False, "Bring your hands to chest level in prayer position", None
            return False, "Stand tall with good posture", None

        elif pose_name == "Downward Dog":
            # Check for inverted V shape, heels toward floor, arms straight
            left_body_angle = calculate_angle(left_shoulder, left_hip, left_ankle)
            right_body_angle = calculate_angle(right_shoulder, right_hip, right_ankle)
            # Relaxed check for downward dog (inverted V) - angle at hip should be acute
            if left_body_angle < 170 and right_body_angle < 170:  # Both sides form inverted V (more relaxed range)
                # Additional check: hips should be higher than shoulders for proper inverted V
                hip_height = (left_hip[1] + right_hip[1]) / 2
                shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
                if hip_height < shoulder_height - 0.05:  # Hips above shoulders (relaxed threshold)
                    return True, None, None
                return False, "Lift your hips higher to form a proper inverted V shape", None
            return False, "Lift your hips up and back to form an inverted V shape", None

        elif pose_name == "Bridge Pose":
            # Check if lying on back with hips lifted - extremely relaxed
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2

            # Hips should be higher than shoulders (bridge position) - extremely relaxed
            if hip_height < shoulder_height - 0.05:  # Extremely relaxed hip lift threshold
                # Check if knees are bent (typical for bridge pose) - extremely relaxed
                left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
                right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
                if left_knee_angle < 170 and right_knee_angle < 170:  # Knees bent (extremely relaxed)
                    # Check if back is straight - extremely relaxed
                    back_angle = calculate_angle(left_shoulder, left_hip, left_knee)
                    if 120 < back_angle < 240:  # Extremely relaxed range for straight back
                        return True, None, None
                    return False, "Keep your back straight while lifting hips", None
                return False, "Bend your knees and keep feet flat on the ground", None
            return False, "Lift your hips higher toward the ceiling", None


        elif pose_name == "Plank Pose":
            body_angle = calculate_angle(left_shoulder, left_hip, left_ankle)
            # Relaxed straight line check
            if 170 < body_angle < 190:
                return True, None, None
            return False, "Keep your body in a straight line from head to heels", None

        elif pose_name == "Easy Standing Forward Bend":
            # Check if person is bending forward
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            hip_height = (left_hip[1] + right_hip[1]) / 2
            if shoulder_height > hip_height + 0.02:  # Shoulders below hips (more relaxed threshold)
                return True, None, None
            return False, "Bend forward from your hips, keeping your back relaxed", None

        elif pose_name == "Standing Side Bend":
            # Check for side bend (one shoulder higher than the other)
            shoulder_diff = abs(left_shoulder[1] - right_shoulder[1])
            if shoulder_diff > 0.05:  # Relaxed threshold for side bend
                return True, None, None
            return False, "Raise one arm overhead and lean to the side", None

        elif pose_name == "Easy Warrior":
            # Check for gentle warrior stance
            shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
            left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)

            # Check for slight wide stance and gentle knee bend
            if shoulder_width > 0.1 and (left_knee_angle < 160 or right_knee_angle < 160):
                return True, None, None
            return False, "Step one foot back slightly and bend your front knee gently", None


        elif pose_name == "Easy Pose":
            # Check if sitting cross-legged with better detection
            hip_height = (left_hip[1] + right_hip[1]) / 2
            knee_height = (left_knee[1] + right_knee[1]) / 2

            # Person should be sitting (hips relatively high)
            if hip_height > 0.6:
                # Check if knees are apart (cross-legged position)
                knee_distance = abs(left_knee[0] - right_knee[0])
                if knee_distance > 0.15:  # Knees should be apart for cross-legged
                    return True, None, None
                return False, "Open your knees wider and cross your shins", None
            return False, "Sit comfortably on the floor with legs crossed", None

        elif pose_name == "Seated Twist":
            # Check for spinal twist
            shoulder_alignment = abs(left_shoulder[1] - right_shoulder[1])
            if shoulder_alignment > 0.03:  # Shoulders not level indicates twist - relaxed threshold
                return True, None, None
            return False, "Gently twist your spine while keeping it long", None

        elif pose_name == "Butterfly Pose":
            # Check if knees are open (butterfly position)
            knee_distance = abs(left_knee[0] - right_knee[0])
            if knee_distance > 0.15:  # Knees apart - relaxed threshold
                return True, None, None
            return False, "Bring soles of feet together and let knees fall open", None



        elif pose_name == "Camel Pose":
            # Check for back arch with hands reaching toward heels (relaxed constraints)
            back_angle = calculate_angle(left_shoulder, left_hip, left_knee)
            # Kneeling position with arched back - relaxed threshold
            if back_angle > 120:  # More relaxed arch requirement
                # Check if at least one hand is reaching back (wrists behind hips) - relaxed
                if left_wrist[1] > left_hip[1] - 0.1 or right_wrist[1] > right_hip[1] - 0.1:
                    return True, None, None
                return False, "Reach your hands toward your heels while arching your back", None
            return False, "Arch your back and place hands on lower back first", None

        elif pose_name == "Hero Pose":
            # Check kneeling with knees together and sitting between heels (relaxed constraints)
            knee_distance = abs(left_knee[0] - right_knee[0])
            hip_height = (left_hip[1] + right_hip[1]) / 2
            ankle_height = (left_ankle[1] + right_ankle[1]) / 2
            knee_angle = calculate_angle(left_hip, left_knee, left_ankle)

            # First check if kneeling (knees bent)
            if knee_angle < 150:  # Knees should be bent for kneeling
                if knee_distance < 0.25:  # More relaxed knee proximity
                    if hip_height > ankle_height - 0.1:  # Relaxed sitting requirement (hips below ankles)
                        return True, None, None
                    return False, "Sit back between your heels", None
                return False, "Bring your knees closer together", None
            return False, "Kneel with your knees together first", None

        elif pose_name == "Chair Pose":
            # Check squatting position with arms raised (relaxed constraints)
            knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            if knee_angle < 160:  # More relaxed knee bend requirement
                # Check arms raised overhead - at least one arm raised above shoulder
                if left_wrist[1] < left_shoulder[1] - 0.1 or right_wrist[1] < right_shoulder[1] - 0.1:
                    return True, None, None
                return False, "Raise your arms overhead", None
            return False, "Bend your knees as if sitting back into a chair", None

        elif pose_name == "Mountain Pose":
            # Check standing tall with arms at sides - extremely relaxed
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            hip_height = (left_hip[1] + right_hip[1]) / 2
            wrist_height = (left_wrist[1] + right_wrist[1]) / 2

            # Person should be standing (shoulders above hips) - extremely relaxed
            if shoulder_height < hip_height:  # Shoulders should be above hips for standing
                # Arms should be roughly at sides - extremely lenient
                if wrist_height > hip_height - 0.2 and wrist_height < shoulder_height + 0.2:  # Arms at sides - extremely relaxed
                    # Feet reasonably close together - extremely relaxed
                    ankle_distance = abs(left_ankle[0] - right_ankle[0])
                    if ankle_distance < 1.0:  # Feet together or hip-width - extremely relaxed
                        return True, None, None
                    return False, "Stand with feet together or hip-width apart", None
                return False, "Let your arms hang naturally at your sides", None
            return False, "Stand tall with good posture", None

        elif pose_name == "Child Pose":
            # Check kneeling with knees wide and folding forward - extremely relaxed
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            knee_distance = abs(left_knee[0] - right_knee[0])

            # Person should be kneeling (hips low in frame) and folded forward - extremely relaxed
            if hip_height > 0.7 and shoulder_height > hip_height:  # Extremely relaxed kneeling and folded forward
                # Knees should be apart (wide kneeling position) - extremely relaxed
                if knee_distance > 0.04:  # Knees wide apart - extremely relaxed
                    return True, None, None  # Allow without strict arm extension
                return False, "Widen your knees apart", None
            return False, "Kneel and fold forward, resting your forehead toward the floor", None

        elif pose_name == "Seated Forward Bend":
            # Check sitting with legs extended and folding forward - extremely relaxed
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
            knee_height = (left_knee[1] + right_knee[1]) / 2

            # Person should be sitting (hips relatively high) - extremely relaxed
            if hip_height > 0.5:
                # Legs should be extended straight (knees relatively low) - extremely relaxed
                if knee_height > 0.6:  # Knees extended - extremely relaxed
                    # Should be bending forward (shoulders below hip level) - extremely relaxed
                    if shoulder_height > hip_height + 0.03:  # Forward fold - extremely relaxed
                        return True, None, None
                    return False, "Fold forward from your hips, reaching toward your feet", None
                return False, "Extend your legs straight out in front of you", None
            return False, "Sit on the floor with legs extended", None

        elif pose_name == "Cat Pose":
            # Check on hands and knees with back arched upward - extremely relaxed
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2

            # Person should be on hands and knees (hips and shoulders at similar height) - extremely relaxed
            if abs(hip_height - shoulder_height) < 0.25:  # Hands and knees position - extremely relaxed
                # Back should be arched upward (shoulders higher than hips for cat arch) - extremely relaxed
                if shoulder_height < hip_height - 0.03:  # Arched back upward - extremely relaxed
                    return True, None, None
                return False, "Arch your back upward like a cat", None
            return False, "Start on your hands and knees", None

        elif pose_name == "Cow Pose":
            # Check on hands and knees with back arched downward - extremely relaxed
            hip_height = (left_hip[1] + right_hip[1]) / 2
            shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2

            # Person should be on hands and knees (hips and shoulders at similar height) - extremely relaxed
            if abs(hip_height - shoulder_height) < 0.25:  # Hands and knees position - extremely relaxed
                # Back should be arched downward (hips higher than shoulders for cow arch) - extremely relaxed
                if hip_height < shoulder_height - 0.03:  # Arched back downward - extremely relaxed
                    return True, None, None
                return False, "Arch your back downward, lifting your chest and gaze", None
            return False, "Start on your hands and knees", None

        # For other poses, use general checking
        shoulder_alignment = abs(left_shoulder[1] - right_shoulder[1])
        hip_alignment = abs(left_hip[1] - right_hip[1])

        if shoulder_alignment < 0.02 and hip_alignment < 0.02:
            return True, None, None
        return False, "Your posture is not perfect. Align shoulders and hips perfectly.", None

    def detect_wrong_pose(self, landmarks):
        """Detect if user is doing a different pose than selected"""
        def lm(index):
            return [landmarks[index].x, landmarks[index].y]

        left_shoulder = lm(11)
        right_shoulder = lm(12)
        left_elbow = lm(13)
        right_elbow = lm(14)
        left_wrist = lm(15)
        right_wrist = lm(16)
        left_hip = lm(23)
        right_hip = lm(24)
        left_knee = lm(25)
        right_knee = lm(26)
        left_ankle = lm(27)
        right_ankle = lm(28)

        # Check for Tree Pose (one foot raised)
        left_foot_height = left_ankle[1]
        right_foot_height = right_ankle[1]
        foot_height_diff = abs(left_foot_height - right_foot_height)
        if foot_height_diff > 0.15:
            return "Tree Pose"

        # Check for Warrior poses (wide stance)
        shoulder_width = abs(left_shoulder[0] - right_shoulder[0])
        if shoulder_width > 0.3:  # Wide stance
            # Check knee bend for Warrior
            left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
            right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)
            if left_knee_angle < 120 or right_knee_angle < 120:
                return "Warrior Pose"

        # Check for Plank (straight body line)
        body_angle = calculate_angle(left_shoulder, left_hip, left_ankle)
        if 170 < body_angle < 190:
            return "Plank Pose"

        # Check for Chair Pose (squatting with arms raised)
        knee_angle = calculate_angle(left_hip, left_knee, left_ankle)
        if knee_angle < 140:  # Knees bent
            # Check if arms are raised overhead
            if left_wrist[1] < left_shoulder[1] + 0.1 or right_wrist[1] < right_shoulder[1] + 0.1:
                return "Chair Pose"

        # Check for Bridge Pose (lying on back with hips lifted)
        hip_height = (left_hip[1] + right_hip[1]) / 2
        shoulder_height = (left_shoulder[1] + right_shoulder[1]) / 2
        if hip_height < shoulder_height - 0.1:
            return "Bridge Pose"

        # Check for Camel Pose (kneeling with arched back and hands reaching back)
        back_angle = calculate_angle(left_shoulder, left_hip, left_knee)
        if back_angle > 140:  # Arched back
            # Check if hands are reaching back
            if left_wrist[1] > left_hip[1] - 0.05 or right_wrist[1] > right_hip[1] - 0.05:
                return "Camel Pose"

        # Check for Hero Pose (kneeling with knees together and sitting between heels)
        knee_distance = abs(left_knee[0] - right_knee[0])
        hip_height = (left_hip[1] + right_hip[1]) / 2
        ankle_height = (left_ankle[1] + right_ankle[1]) / 2
        if knee_distance < 0.15 and hip_height > ankle_height:
            return "Hero Pose"

        return None  # No specific wrong pose detected

    def start_breathing(self):
        """Start the breathing exercise animation"""
        # COMMENTED OUT AS PER LATEST REQUIREMENTS
        # if not self.breathing_active:
        #     self.breathing_active = True
        #     self.breathing_phase = 0
        #     self.breathing_size = 30
        #     self.breathing_btn.config(text="Stop", command=self.stop_breathing, bg="#d63031")
        #     Thread(target=self.animate_breathing, daemon=True).start()

        # TEMPORARY FEEDBACK FOR BUTTON PRESS
        self.update_status("Breathing exercise started (not yet animated)")

    def stop_breathing(self):
        """Stop the breathing exercise"""
        # COMMENTED OUT AS PER LATEST REQUIREMENTS
        # self.breathing_active = False
        # self.breathing_btn.config(text="Start →", command=self.start_breathing, bg="#00b894")
        # self.breathing_canvas.itemconfig(self.breathing_status, text="Ready")
        # self.breathing_canvas.itemconfig(self.breathing_subtext, text="Breathe and Relax")
        # self.breathing_timer_label.config(text="")
        # self.breathing_canvas.coords(self.breathing_circle, 60, 60, 120, 120)

        # TEMPORARY FEEDBACK FOR BUTTON PRESS
        self.update_status("Breathing exercise stopped (not yet animated)")

    def animate_breathing(self):
        """Animate the breathing circle and provide instructions"""
        # COMMENTED OUT AS PER LATEST REQUIREMENTS
        # Inhale (4s)
        # self.breathing_canvas.itemconfig(self.breathing_status, text="Inhale")
        # self.breathing_canvas.itemconfig(self.breathing_subtext, text="Fill your
        # speak("Inhale slowly")
        # for t in range(4, 0, -1):
        #     if not self.breathing_active: return
        #     self.breathing_timer_label.config(text=f"{t}")
        #     # Animate circle growing
        #     size = 30 + (4-t)*7
        #     self.breathing_canvas.coords(self.breathing_circle, 90-size, 90-size, 90+size, 90+size)
        #     time.sleep(1)
        # self.breathing_timer_label.config(text="")
        #
        # # Hold (8s)
        # self.breathing_canvas.itemconfig(self.breathing_status, text="Hold")
        # self.breathing_canvas.itemconfig(self.breathing_subtext, text="Pause and relax")
        # speak("Hold your breath")
        # for t in range(8, 0, -1):
        #     if not self.breathing_active: return
        #     self.breathing_timer_label.config(text=f"{t}")
        #     time.sleep(1)
        # self.breathing_timer_label.config(text="")
        #
        # # Exhale (4s)
        # self.breathing_canvas.itemconfig(self.breathing_status, text="Exhale")
        # self.breathing_canvas.itemconfig(self.breathing_subtext, text="Release slowly")
        # speak("Exhale slowly")
        # for t in range(4, 0, -1):
        #     if not self.breathing_active: return
        #     self.breathing_timer_label.config(text=f"{t}")
        #     # Animate circle shrinking
        #     size = 58 - (4-t)*7
        #     self.breathing_canvas.coords(self.breathing_circle, 90-size, 90-size, 90+size, 90+size)
        #     time.sleep(1)
        # self.breathing_timer_label.config(text="")
        # self.stop_breathing()

        # TEMPORARY FEEDBACK FOR BUTTON PRESS
        self.update_status("Breathing animation (not yet implemented)")

    def __del__(self):
        """Cleanup"""
        self.running = False
        self.breathing_active = False

if __name__ == "__main__":
    root = tk.Tk()
    app = YogaMateApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (setattr(app, 'running', False), root.destroy()))
    root.mainloop()

# BreathingExerciseWidget.py (or place inside your main file as a class)

class BreathingExerciseWidget(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, bg="#0a3d62", *args, **kwargs)
        self.breathing_active = False
        self.breathing_size = 30

        # Voice engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        self.engine.setProperty('volume', 0.9)

        # Canvas for circle and text
        self.breathing_canvas = tk.Canvas(
            self, width=180, height=180, bg="#0a3d62", highlightthickness=0
        )
        self.breathing_canvas.pack(pady=0)

        self.breathing_circle = self.breathing_canvas.create_oval(
            60, 60, 120, 120, fill="#1e90ff", outline="#60a3bc", width=4
        )
        self.breathing_status = self.breathing_canvas.create_text(
            90, 80, text="Ready", font=("Poppins", 20, "bold"), fill="#fff"
        )
        self.breathing_subtext = self.breathing_canvas.create_text(
            90, 110, text="Breathe and Relax", font=("Poppins", 12), fill="#dff9fb"
        )

        self.breathing_timer_label = tk.Label(
            self, text="", font=("Poppins", 18, "bold"),
            bg="#0a3d62", fg="#dff9fb"
        )
        self.breathing_timer_label.pack(pady=(8,0))

        self.breathing_btn = tk.Button(
            self, text="Start →", font=("Poppins", 13, "bold"),
            bg="#00b894", fg="#fff", activebackground="#0984e3",
            relief="flat", width=12, bd=0, command=self.start_breathing,
            cursor="hand2", highlightthickness=0
        )
        self.breathing_btn.pack(pady=16)

    def speak(self, text):
        def speak_thread():
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except:
                pass
        Thread(target=speak_thread, daemon=True).start()

    def start_breathing(self):
        if not self.breathing_active:
            self.breathing_active = True
            self.breathing_btn.config(text="Stop", command=self.stop_breathing, bg="#d63031")
            Thread(target=self.animate_breathing, daemon=True).start()

    def stop_breathing(self):
        self.breathing_active = False
        self.breathing_btn.config(text="Start →", command=self.start_breathing, bg="#00b894")
        self.breathing_canvas.itemconfig(self.breathing_status, text="Ready")
        self.breathing_canvas.itemconfig(self.breathing_subtext, text="Breathe and Relax")
        self.breathing_timer_label.config(text="")
        self.breathing_canvas.coords(self.breathing_circle, 60, 60, 120, 120)

    def animate_breathing(self):
        # Inhale (4s)
        self.breathing_canvas.itemconfig(self.breathing_status, text="Inhale")
        self.breathing_canvas.itemconfig(self.breathing_subtext, text="Fill your lungs")
        self.speak("Inhale slowly")
        for t in range(4, 0, -1):
            if not self.breathing_active: return
            self.breathing_timer_label.config(text=f"{t}")
            # Animate circle growing
            size = 30 + (4-t)*7
            self.breathing_canvas.coords(self.breathing_circle, 90-size, 90-size, 90+size, 90+size)
            time.sleep(1)
        self.breathing_timer_label.config(text="")

        # Hold (8s)
        self.breathing_canvas.itemconfig(self.breathing_status, text="Hold")
        self.breathing_canvas.itemconfig(self.breathing_subtext, text="Pause and relax")
        self.speak("Hold your breath")
        for t in range(8, 0, -1):
            if not self.breathing_active: return
            self.breathing_timer_label.config(text=f"{t}")
            time.sleep(1)
        self.breathing_timer_label.config(text="")

        # Exhale (4s)
        self.breathing_canvas.itemconfig(self.breathing_status, text="Exhale")
        self.breathing_canvas.itemconfig(self.breathing_subtext, text="Release slowly")
        self.speak("Exhale slowly")
        for t in range(4, 0, -1):
            if not self.breathing_active: return
            self.breathing_timer_label.config(text=f"{t}")
            # Animate circle shrinking
            size = 58 - (4-t)*7
            self.breathing_canvas.coords(self.breathing_circle, 90-size, 90-size, 90+size, 90+size)
            time.sleep(1)
        self.breathing_timer_label.config(text="")
        self.stop_breathing()

# Example usage:
# root = tk.Tk()
# breathing_widget = BreathingExerciseWidget(root)
# breathing_widget.pack()
# root.mainloop()
