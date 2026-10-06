import cv2

cap = cv2.VideoCapture(0)
#4 - side 2 - top
while True:
    ret, frame = cap.read()
    if not ret:
        break
    cv2.imshow('Webcam', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
cv2.destroyAllWindows()
# This code captures video from the webcam and displays it in a window.