"""CNN-only inference script for WHO Hand Wash Step Recognition.

This module provides the single source of truth for hand wash step inference.
MediaPipe has been completely eliminated - all predictions come from the CNN model.
"""

import cv2
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from torchvision import models, transforms
from PIL import Image

# --- CONFIGURATION ---
CONFIG = {
    "IMG_SIZE": 160,  # MobileNet input size
}
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CLASSES = ["Background", "Palm", "Dorsum", "Interlaced", "Interlocked", "Thumbs", "Fingertips"]


# --- MODEL ARCHITECTURE (Single Source of Truth) ---
class CNNModel(nn.Module):
    """MobileNetV3-Small based classifier for hand wash step recognition."""
    
    def __init__(self, num_classes=7):
        super().__init__()
        try:
            self.backbone = models.mobilenet_v3_small(weights=None)
        except TypeError:
            self.backbone = models.mobilenet_v3_small(pretrained=False)
        self.backbone.classifier[3] = nn.Linear(1024, num_classes)

    def forward(self, x):
        return self.backbone(x)


# --- CNN-ONLY INFERENCE ENGINE ---
class DeltaWashEngine:
    """CNN-only inference engine for WHO hand wash step recognition.
    
    This is the single source of truth for all step predictions.
    """
    
    def __init__(self, cnn_path="cnn_model.pth", **kwargs):
        """Initialize the CNN engine.
        
        Args:
            cnn_path: Path to the CNN model weights.
            **kwargs: Ignored for backwards compatibility (lstm_path, etc.).
        """
        self.transform = transforms.Compose([
            transforms.Resize((CONFIG["IMG_SIZE"], CONFIG["IMG_SIZE"])),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        # Initialize and load model
        self.cnn = CNNModel(len(CLASSES))
        self._load_weights(cnn_path)

    def _load_weights(self, path):
        """Load model weights from file."""
        try:
            self.cnn.load_state_dict(torch.load(path, map_location=DEVICE))
            self.cnn.to(DEVICE).eval()
            print(f"✅ CNN Model loaded from {path}")
        except Exception as e:
            print(f"⚠️ Warning: Could not load {path}. Error: {e}")
            self.cnn = None

    def predict(self, frame, is_target_frame=True):
        """Run inference on a single frame.
        
        Args:
            frame: BGR frame as numpy array (from OpenCV)
            is_target_frame: Ignored (kept for backwards compatibility)
            
        Returns:
            Tuple of (label, confidence, landmarks, status, cnn_probs, lstm_probs)
            Note: landmarks is always None, lstm_probs mirrors cnn_probs
        """
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # CNN STREAM
        cnn_probs = np.zeros(len(CLASSES))
        if self.cnn:
            img_pil = Image.fromarray(frame_rgb)
            img_t = self.transform(img_pil).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                logits = self.cnn(img_t)
                cnn_probs = F.softmax(logits, dim=1).cpu().numpy()[0]

        # Determine final prediction
        idx = np.argmax(cnn_probs)
        conf = cnn_probs[idx]
        
        # Threshold: if CNN is not confident, default to Background
        if conf < 0.40:
            idx = 0
            conf = cnn_probs[0]

        status = "CNN Only"
        
        # Return in legacy format for backwards compatibility
        # landmarks=None since we don't use MediaPipe anymore
        # lstm_probs mirrors cnn_probs since there's no LSTM
        return CLASSES[idx], conf, None, status, cnn_probs, cnn_probs


def main():
    """Standalone test loop for CNN inference."""
    cap = cv2.VideoCapture(0)
    engine = DeltaWashEngine()
    frame_count = 0
    
    print("🚀 CNN-Only Inference Started. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Run inference
        label, confidence, landmarks, mode, cnn_p, lstm_p = engine.predict(frame, True)
        
        # Draw HUD
        color = (0, 255, 0) if label != "Background" else (200, 200, 200)
        cv2.rectangle(frame, (0, 0), (350, 80), (0, 0, 0), -1)
        cv2.putText(frame, f"{label}", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"Conf: {confidence:.0%}", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        cv2.putText(frame, f"Mode: {mode}", (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.imshow("WHO Hand Wash Recognition (CNN-Only)", frame)
        frame_count += 1
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
