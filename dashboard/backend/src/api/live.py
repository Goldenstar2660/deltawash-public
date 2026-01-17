import cv2
import asyncio
import time
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..services.visualizer import visualizer_service

router = APIRouter(tags=["live"])

class UpdateRequest(BaseModel):
    label: str

def generate_frames():
    """Generator function for MJPEG stream."""
    if not visualizer_service:
        # Return a black frame or error image if service failed to load
        return

    while True:
        frame = visualizer_service.get_output_frame()
        
        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        
        # Yield the frame in MJPEG format
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        # Limit framerate to ~10 FPS to save bandwidth/cpu
        time.sleep(0.1)

@router.get("/stream")
async def video_feed():
    """Stream the generated wash visualization."""
    if not visualizer_service:
        raise HTTPException(status_code=503, detail="Visualizer service not available (check assets)")
        
    return StreamingResponse(generate_frames(), 
                             media_type='multipart/x-mixed-replace; boundary=frame')

@router.post("/update")
async def update_state(request: UpdateRequest):
    """Update the wash state with a new classification label."""
    if not visualizer_service:
        raise HTTPException(status_code=503, detail="Visualizer service not available")
    
    visualizer_service.update(request.label)
    return {"status": "updated", "current_state": visualizer_service.states}
