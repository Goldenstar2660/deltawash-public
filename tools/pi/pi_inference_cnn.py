import time
import sys
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image
import numpy as np

# ==========================================
# 1. SETUP & IMPORTS
# ==========================================
try:
    from picamera2 import Picamera2
except ImportError:
    print("❌ Error: 'picamera2' library not found.")
    print("   Run: sudo apt install python3-picamera2")
    sys.exit(1)

CONFIG = {
    # We use 160x160 to match the MobileNet input size directly.
    # This offloads resizing to the camera hardware (ISP).
    "IMG_SIZE": 160, 
    "CLASSES": ["Background", "Palm", "Dorsum", "Interlaced", "Interlocked", "Thumbs", "Fingertips"],
    "MODEL_PATH": "cnn_model.pth"
}

DEVICE = torch.device("cpu")

# ==========================================
# 2. MODEL ARCHITECTURE
# ==========================================
class CNNModel(nn.Module):
    def __init__(self):
        super().__init__()
        # Handle different torchvision versions (weights vs pretrained)
        try:
            self.backbone = models.mobilenet_v3_small(weights=None)
        except TypeError:
            self.backbone = models.mobilenet_v3_small(pretrained=False)
            
        # Modify classifier to match 7 classes
        self.backbone.classifier[3] = nn.Linear(1024, len(CONFIG["CLASSES"]))

    def forward(self, x):
        return self.backbone(x)

# ==========================================
# 3. INFERENCE ENGINE
# ==========================================
class PiInferenceEngine:
    def __init__(self, model_path):
        print(f"⏳ Loading Model from {model_path}...")
        
        # Preprocessing: Only ToTensor and Normalize needed.
        # Resizing is done by the camera hardware now.
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

        self.model = CNNModel()
        try:
            state_dict = torch.load(model_path, map_location=DEVICE)
            self.model.load_state_dict(state_dict)
            self.model.to(DEVICE)
            self.model.eval()
            print("✅ Model Loaded Successfully")
        except FileNotFoundError:
            print(f"❌ Error: '{model_path}' not found.")
            sys.exit(1)
        except RuntimeError as e:
            print(f"❌ Shape Mismatch: {e}")
            print("   Ensure the number of classes in CONFIG matches your training data.")
            sys.exit(1)

        # --- CAMERA SETUP ---
        print("📷 Initializing Picamera2...")
        self.picam2 = Picamera2()
        
        # FIX: Use 'create_video_configuration' instead of 'create_configuration'
        # This is the compatible method for your version of Picamera2.
        config = self.picam2.create_video_configuration(
            main={
                "size": (CONFIG["IMG_SIZE"], CONFIG["IMG_SIZE"]), 
                "format": "RGB888"
            }
        )
        
        self.picam2.configure(config)
        self.picam2.start()
        print(f"✅ Camera Started (Hardware Resizing to {CONFIG['IMG_SIZE']}x{CONFIG['IMG_SIZE']})")

    def predict(self, array_rgb):
        # Convert Numpy -> PIL Image
        # (This step ensures compatibility with torchvision transforms)
        img = Image.fromarray(array_rgb)
        
        # Preprocess
        input_tensor = self.transform(img).unsqueeze(0).to(DEVICE)
        
        # Inference
        with torch.no_grad():
            output = self.model(input_tensor)
            probs = F.softmax(output, dim=1)
            conf, idx = torch.max(probs, 1)
            
        return CONFIG["CLASSES"][idx.item()], conf.item()

    def run_loop(self):
        print("\n🚀 Starting Inference Loop (Press Ctrl+C to stop)...")
        print(f"{'PREDICTION':<15} | {'CONFIDENCE':<10} | {'FPS':<5}")
        print("-" * 40)

        try:
            frame_count = 0
            start_time = time.time()
            
            while True:
                # Capture directly into numpy array (uses the 'main' config we set above)
                frame = self.picam2.capture_array()

                # Run Inference
                label, conf = self.predict(frame)

                # FPS Calculation
                frame_count += 1
                elapsed = time.time() - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0

                # Color output (Green for hand gestures, Grey for background)
                color = "\033[92m" if label != "Background" else "\033[90m"
                reset = "\033[0m"
                
                # Print Result
                sys.stdout.write(f"\r{color}{label:<15}{reset} | {conf:.1%}      | {fps:.1f} ")
                sys.stdout.flush()

                # Reset FPS counter every 5 seconds
                if elapsed > 5:
                    frame_count = 0
                    start_time = time.time()

        except KeyboardInterrupt:
            print("\n\n🛑 Stopping...")
            self.picam2.stop()
            print("Camera Released.")

# ==========================================
# 4. EXECUTE
# ==========================================
if __name__ == "__main__":
    engine = PiInferenceEngine(CONFIG["MODEL_PATH"])
    engine.run_loop()
