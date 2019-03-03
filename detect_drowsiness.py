from scipy.spatial import distance as dist
from imutils.video import VideoStream
from imutils import face_utils
from threading import Thread
import findGasStation as assist
import serial
import alarmSignalSerial as arduino
import numpy as np
import playsound
import argparse
import imutils
import time
import dlib
import cv2


def sound_alarm(path):
    # play an alarm sound
    playsound.playsound(path)


def eye_aspect_ratio(eye):
    # compute the euclidean distances between the two sets of
    # vertical eye landmarks (x, y)-coordinates
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])

    # compute the euclidean distance between the horizontal
    # eye landmark (x, y)-coordinates
    C = dist.euclidean(eye[0], eye[3])

    # compute the eye aspect ratio
    ear = (A + B) / (2.0 * C)

    # return the eye aspect ratio
    return ear


# define constants

modelPath = 'shape_predictor_68_face_landmarks.dat'
alarmPath = 'alarm.wav'
EYE_AR_THRESH = 0.28
EYE_AR_CONSEC_FRAMES = 30

# initialize the frame counter as well as a boolean used to
# indicate if the alarm is going off
COUNTER = 0
ALARM_ON = False

WARNING_PLAYED = False
warningsInPeriod = 0
currPeriodLength = 0
MAX_WARNINGS_THRESH = 3
MAX_PERIOD_THRESH = 30000

# initialize ardunio connection
serPort = "/dev/cu.usbmodem141101"
baudRate = 9600
ser = serial.Serial(serPort, baudRate)
arduino.waitForArduino(ser)

# initialize facial detector
print("[INFO] loading facial landmark predictor...")
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(modelPath)

# grab the indexes of the facial landmarks for the left and
# right eye, respectively
(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]

# start the video stream thread
print("[INFO] starting video stream thread...")
vs = VideoStream(0).start()
time.sleep(1.0)

# loop over frames from the video stream
while True:
    # grab the frame from the threaded video file stream, resize
    # it, and convert it to grayscale
    # channels)
    frame = vs.read()
    frame = imutils.resize(frame, width=450)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # increment timer and check if we should reset warning count
    currPeriodLength += 1
    if (currPeriodLength >= MAX_PERIOD_THRESH):
        #reset warning counter
        currPeriodLength = 0
        warningsInPeriod = 0

    # detect faces in the grayscale frame
    rects = detector(gray, 0)

    # loop over the face detections
    for rect in rects:
        # determine the facial landmarks for the face region, then
        # convert the facial landmark (x, y)-coordinates to a NumPy
        # array
        shape = predictor(gray, rect)
        shape = face_utils.shape_to_np(shape)

        # extract the left and right eye coordinates, then use the
        # coordinates to compute the eye aspect ratio for both eyes
        leftEye = shape[lStart:lEnd]
        rightEye = shape[rStart:rEnd]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)

        # average the eye aspect ratio together for both eyes
        ear = (leftEAR + rightEAR) / 2.0

        # compute the convex hull for the left and right eye, then
        # visualize each of the eyes
        leftEyeHull = cv2.convexHull(leftEye)
        rightEyeHull = cv2.convexHull(rightEye)
        cv2.drawContours(frame, [leftEyeHull], -1, (0, 255, 0), 1)
        cv2.drawContours(frame, [rightEyeHull], -1, (0, 255, 0), 1)

        # check to see if the eye aspect ratio is below the blink
        # threshold, and if so, increment the blink frame counter
        if ear < EYE_AR_THRESH:
            COUNTER += 1

            # if the eyes were closed for a sufficient number of
            # then sound the alarm
            if COUNTER >= EYE_AR_CONSEC_FRAMES:

                # if the alarm is not on, turn it on
                if not ALARM_ON:
                    ALARM_ON = True
                    warningsInPeriod += 1
                        
                    # start a thread to have the alarm
                    # sound played in the background
                    t = Thread(target=sound_alarm,
                            args=(alarmPath,))
                    t.deamon = True
                    t.start()

                    # check to see if this is the third warning and we've only triggered the alarm once
                    if (warningsInPeriod >= MAX_WARNINGS_THRESH and not WARNING_PLAYED):
                        
                        # play audio warning
                        WARNING_PLAYED = True
                        t = Thread(target=assist.giveLocationWarning)
                        t.deamon = True
                        t.start()

                    

                # send arduino to start vibration
                arduino.sendAlarmSignal(1, ser)

        # otherwise, the eye aspect ratio is not below the blink
        # threshold, so reset the counter and alarm
        else:
            COUNTER = 0
            ALARM_ON = False
            arduino.sendAlarmSignal(0, ser)

        # draw the computed eye aspect ratio on the frame to help
        # with debugging and setting the correct eye aspect ratio
        # thresholds and frame counters
        cv2.putText(frame, "EAR: {:.2f}".format(ear), (300, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                                    # draw an alarm on the frame
        cv2.putText(frame, "WARNING COUNT: {:.2f}".format(warningsInPeriod), (200, 230),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # show the frame
    cv2.imshow("Frame", frame)
    key = cv2.waitKey(1) & 0xFF

    # if the `q` key was pressed, break from the loop
    if key == ord("q"):
        break

# do a bit of cleanup
cv2.destroyAllWindows()
vs.stop()
ser.close
