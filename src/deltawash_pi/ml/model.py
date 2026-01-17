"""CNN-only WHO Hand Wash Step Recognizer.

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
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
CONFIG = {
    "IMG_SIZE": 160,  # MobileNet input size
    "CLASSES": ["Background", "Palm", "Dorsum", "Interlaced", "Interlocked", "Thumbs", "Fingertips"],
}

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ==========================================
# MODEL ARCHITECTURE (Single Source of Truth)
# ==========================================
class CNNModel(nn.Module):
    """MobileNetV3-Small based classifier for hand wash step recognition."""
    
    def __init__(self, num_classes=7):
        super().__init__()
        # Handle different torchvision versions (weights vs pretrained)
        try:
            self.backbone = models.mobilenet_v3_small(weights=None)
        except TypeError:
            self.backbone = models.mobilenet_v3_small(pretrained=False)
        
        # Modify classifier to match number of classes
        self.backbone.classifier[3] = nn.Linear(1024, num_classes)

    def forward(self, x):
        return self.backbone(x)


# ==========================================
# INFERENCE ENGINE (CNN-Only)
# ==========================================
class DeltaWashAnalyzer:
    """CNN-only inference engine for WHO hand wash step recognition.
    
    This is the single source of truth for all step predictions.
    No MediaPipe or LSTM - pure CNN texture-based classification.
    """
    
    def __init__(self, cnn_path: str = None, **kwargs):
        """Initialize the CNN analyzer.
        
        Args:
            cnn_path: Path to the CNN model weights. If None, uses default location.
            **kwargs: Ignored for backwards compatibility (pixel_path, pose_path, lstm_path).
        """
        self.device = DEVICE
        self.classes = CONFIG["CLASSES"]
        
        # Preprocessing: Resize to model input size, normalize
        self.transform = transforms.Compose([
            transforms.Resize((CONFIG["IMG_SIZE"], CONFIG["IMG_SIZE"])),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        # Initialize and load model
        self.model = CNNModel(len(self.classes))
        
        # Determine model path
        if cnn_path is None:
            model_dir = Path(__file__).resolve().parent
            cnn_path = str(model_dir / "cnn_model.pth")
        
        self._load_weights(cnn_path)

    def _load_weights(self, path: str) -> None:
        """Load model weights from file."""
        try:
            state_dict = torch.load(path, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.to(self.device)
            self.model.eval()
            print(f"✅ CNN Model loaded from {path}")
        except FileNotFoundError:
            print(f"❌ Error: '{path}' not found.")
            raise
        except RuntimeError as e:
            print(f"❌ Model shape mismatch: {e}")
            raise

    def predict(self, frame_rgb: np.ndarray) -> tuple[str, float]:
        """Run inference on a single frame.
        
        Args:
            frame_rgb: RGB frame as numpy array (H, W, 3)
            
        Returns:
            Tuple of (label, confidence)
        """
        # Convert to PIL Image
        img = Image.fromarray(frame_rgb)
        
        # Preprocess
        input_tensor = self.transform(img).unsqueeze(0).to(self.device)
        
        # Inference
        with torch.no_grad():
            output = self.model(input_tensor)
            probs = F.softmax(output, dim=1)
            conf, idx = torch.max(probs, 1)
        
        return self.classes[idx.item()], conf.item()

    def process_frame(self, frame: np.ndarray) -> dict:
        """Process a frame and return results in legacy format.
        
        This method provides backwards compatibility with existing code that
        expects the old multi-model output format.
        
        Args:
            frame: BGR frame as numpy array (from OpenCV)
            
        Returns:
            Dict with 'pixel' (label, confidence), 'pose', 'lstm', 'landmarks'
        """
        # Convert BGR to RGB if needed
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = frame
        
        # Run CNN inference
        label, confidence = self.predict(frame_rgb)
        
        # Return in legacy format for backwards compatibility
        # All predictions come from CNN now - pose/lstm are duplicates
        return {
            "pixel": (label, confidence),
            "pose": (label, confidence),  # Same as CNN (no separate pose model)
            "lstm": (label, confidence),   # Same as CNN (no separate LSTM)
            "landmarks": None,             # No MediaPipe landmarks
        }


# ==========================================
# MAIN LOOP (Standalone Testing)
# ==========================================
def main():
    """Standalone test loop for CNN inference."""
    cap = cv2.VideoCapture(0)
    analyzer = DeltaWashAnalyzer()
    
    print("🚀 CNN-Only Inference Started. Press 'q' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Run inference
        res = analyzer.process_frame(frame)
        
        # Draw HUD
        label, confidence = res["pixel"]
        color = (0, 255, 0) if label != "Background" else (200, 200, 200)
        
        cv2.rectangle(frame, (0, 0), (350, 80), (0, 0, 0), -1)
        cv2.putText(frame, f"Step: {label}", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.putText(frame, f"Conf: {confidence:.0%}", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

        cv2.imshow("WHO Hand Wash AI (CNN-Only)", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()