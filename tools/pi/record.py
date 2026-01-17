import subprocess
import os
import datetime

# --- SETTINGS ---
FPS = 30  # Change to 10 if needed
# ----------------

def get_new_filenames():
    """Generates names based on the current time"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    h264_name = f"temp_{timestamp}.h264"
    mp4_name = f"video_{timestamp}.mp4"
    return h264_name, mp4_name

def record_loop():
    print("--- Pi Cam Session Started ---")
    print("Commands: [Enter] = Start/Stop | [q] = Quit program")

    while True:
        user_input = input("\nREADY. Press ENTER to start recording (or 'q' to quit): ").lower()
        
        if user_input == 'q':
            print("Exiting...")
            break

        # 1. Prepare filenames
        temp_h264, final_mp4 = get_new_filenames()

        # 2. Start Recording
        print(f"REC ---> Saving to {final_mp4}")
        process = subprocess.Popen([
            "rpicam-vid", 
            "-t", "0", 
            "--nopreview", 
            "--framerate", str(FPS), 
            "-o", temp_h264
        ])

        # 3. Wait for user to stop
        input("RECORDING... Press ENTER to stop.")
        
        # 4. Stop process
        process.terminate()
        process.wait()

        # 5. Convert to MP4
        print("Finalizing file...")
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-r", str(FPS), 
            "-i", temp_h264, 
            "-c", "copy", 
            final_mp4
        ])

        # 6. Cleanup temp file
        if os.path.exists(temp_h264):
            os.remove(temp_h264)
            
        print(f"DONE! Saved as {final_mp4}")

if __name__ == "__main__":
    try:
        record_loop()
    except KeyboardInterrupt:
        print("\nProgram closed.")
