import cv2
cap = cv2.VideoCapture(0)
ret, frame = cap.read()
if ret:
    cv2.imwrite("test_image.jpg", frame)
    print("✅ Camera working! Check test_image.jpg")
else:
    print("❌ Camera NOT working. Is it plugged in?")
cap.release()
