import time
from picamera2 import Picamera2
from picamera2.encoders import FFmpegVideoEncoder

# 1. Initialize
picam2 = Picamera2()

# 2. Configure for YUV420 (The raw feed)
config = picam2.create_video_configuration(
    main={"size": (1280, 720), "format": "YUV420"}
)
picam2.configure(config)

# 3. Set Global Framerate
fps = 30.0
picam2.set_controls({"FrameRate": fps})

print(f"--- Camera Ready (Pi 5 / IMX708) @ {fps} FPS ---")
picam2.start()

try:
    while True:
        input("\n[IDLE] Press Enter to START recording (Ctrl+C to quit)... ")
        
        filename = f"video_{int(time.time())}.mp4"
        
        # On Pi 5, we create an encoder explicitly. 
        # Bonus: This saves directly to .mp4 so you don't have to convert it!
        encoder = FFmpegVideoEncoder()
        
        picam2.start_recording(encoder, filename, fps=fps)
        print(f"[RECORDING] Writing to: {filename}")
        
        input("[RECORDING] Press Enter to STOP...")
        picam2.stop_recording()
        print("[STOPPED] Video saved.")

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    picam2.stop()
    print("Camera closed.")
