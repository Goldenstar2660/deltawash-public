import cv2
import time
import os
import numpy as np
from pathlib import Path
from typing import Dict, Optional

class WashVisualizer:
    def __init__(self):
        """
        Initialize the WashVisualizer with assets.
        Assets are expected to be in the project root 'assets' folder.
        """
        # Calculate path to assets relative to this file
        # File: dashboard/backend/src/services/visualizer.py
        # Root: ../../../../
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent
        self.assets_dir = project_root / "assets"
        
        # Load base canvases
        dirty_path = self.assets_dir / "canvas_dirty.png"
        clean_path = self.assets_dir / "canvas_clean.png"
        
        # Check existence
        if not dirty_path.exists():
            raise FileNotFoundError(f"Could not find {dirty_path}")
        if not clean_path.exists():
            raise FileNotFoundError(f"Could not find {clean_path}")

        self.canvas_dirty = cv2.imread(str(dirty_path))
        self.canvas_clean = cv2.imread(str(clean_path))
        
        if self.canvas_dirty is None:
            raise ValueError(f"Failed to load image: {dirty_path}")
        if self.canvas_clean is None:
            raise ValueError(f"Failed to load image: {clean_path}")

        # Ensure canvas shapes match (resize clean to dirty if mismatch)
        if self.canvas_dirty.shape != self.canvas_clean.shape:
            self.canvas_clean = cv2.resize(self.canvas_clean, 
                                         (self.canvas_dirty.shape[1], self.canvas_dirty.shape[0]))

        # Load masks
        self.masks: Dict[str, np.ndarray] = {}
        mask_files = {
            "palm": "palm.jpg",
            "dorsum": "dorsum.jpg",
            "thumbs": "thumbs.jpg",
            "fingertips": "fingertips.jpg",
            "interlaced": "interlaced.jpg",
            "interlocked": "interlocked.jpg"
        }

        masks_dir = self.assets_dir / "masks"
        if not masks_dir.exists():
             raise FileNotFoundError(f"Masks directory not found at {masks_dir}")

        for key, filename in mask_files.items():
            path = masks_dir / filename
            # Load as grayscale
            mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                print(f"Warning: Could not load mask {filename} from {path}")
                continue
            
            # Binarize mask (ensure clean 0 or 255 edges)
            _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
            
            # Resize mask to match canvas if necessary
            if mask.shape != self.canvas_dirty.shape[:2]:
                mask = cv2.resize(mask, (self.canvas_dirty.shape[1], self.canvas_dirty.shape[0]))
                
            self.masks[key] = mask

        # Initialize state
        # Keys match the mask keys. Values are boolean (True = Clean, False = Dirty).
        self.states = {key: False for key in self.masks}
        
        # Timer for reset logic
        self.last_hand_time = time.time()
        self.reset_timeout = 5.0 # seconds

    def update(self, label_string: str) -> None:
        """
        Update the state based on the detected label.
        
        Args:
            label_string: The detected class (e.g., 'thumbs', 'palm', 'background').
        """
        current_time = time.time()
        label = label_string.lower().strip()

        if label in self.states:
            # Sticky Latch: Once True, stays True until full reset
            self.states[label] = True
            self.last_hand_time = current_time
        
        else:
            # If label is "background" or unknown, we check if we should reset.
            # We do NOT update self.last_hand_time here if it's background.
            
            # Check for reset condition (5 seconds of no valid hand detection)
            if current_time - self.last_hand_time > self.reset_timeout:
                self._reset_states()

    def _reset_states(self) -> None:
        """Reset all states to False (Dirty)."""
        for key in self.states:
            self.states[key] = False

    def get_output_frame(self) -> np.ndarray:
        """
        Generate the current composite frame.
        
        Returns:
            np.ndarray: The composite image (BGR).
        """
        # Optimization: Create a single combined mask of all currently "clean" areas
        # Start with a black mask (zeros)
        combined_clean_mask = np.zeros(self.canvas_dirty.shape[:2], dtype=np.uint8)
        
        has_clean_areas = False
        for key, is_clean in self.states.items():
            if is_clean and key in self.masks:
                # Add this part's mask to the combined mask
                cv2.bitwise_or(combined_clean_mask, self.masks[key], combined_clean_mask)
                has_clean_areas = True
        
        if not has_clean_areas:
            return self.canvas_dirty.copy()

        # 1. Extract the clean pixels where mask is white
        clean_part = cv2.bitwise_and(self.canvas_clean, self.canvas_clean, mask=combined_clean_mask)
        
        # 2. Extract the dirty pixels where mask is black (inverse)
        dirty_mask_inv = cv2.bitwise_not(combined_clean_mask)
        dirty_part = cv2.bitwise_and(self.canvas_dirty, self.canvas_dirty, mask=dirty_mask_inv)
        
        # 3. Combine them
        final_frame = cv2.add(clean_part, dirty_part)
        
        return final_frame

# Global instance for the application to use
# We initialize it lazily or catch errors to avoid breaking app if assets are missing during build
try:
    visualizer_service = WashVisualizer()
except Exception as e:
    print(f"Failed to initialize WashVisualizer: {e}")
    visualizer_service = None
