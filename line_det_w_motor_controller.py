import numpy as np
import math
import cv2
import time
from MotorControlAPI import MotorController 


ROBOT_SPEED = 20
ONE_SECOND_DELAY = 1000000000
#myVar = MotorController('COMx')
motorObj = MotorController('COM4')


def color_filter(image):
    #convert from RGB to HLS (Hue, Lightness, Saturation)
    hls = cv2.cvtColor(image, cv2.COLOR_RGB2HLS)
    lower = np.array([0,190,0])
    upper = np.array([255,255,255])

 
    whitemask = cv2.inRange(hls, lower, upper)
    
    masked = cv2.bitwise_and(image, image, mask = whitemask)    
    


    return masked

def roi(img):
    #function to idenify region of interest, using a triangle to focus on where the lines are
    if img is not None:
        x = int(img.shape[1])
        y = int(img.shape[0])
        shape = np.array([[int(0), int(y)], [int(x), int(y)], [int(0.55*x), int(0.6*y)], [int(0.45*x), int(0.6*y)]])

        mask = np.zeros_like(img)

        #Uses 3 channels or 1 channel for color depending on input image
        if len(img.shape) > 2:
            channel_count = img.shape[2]
            ignore_mask_color = (255,) * channel_count
        else:
            ignore_mask_color = 255

        #creates a polygon with the mask color (for area between lines)
        cv2.fillPoly(mask, np.int32([shape]), ignore_mask_color)

        #returns the image only where the mask pixels are not zero
        masked_image = cv2.bitwise_and(img, mask)
        return masked_image
    else: 
        print("None")

def grayscale(img):
    #canny needs a gray image, so we convert
    return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

def canny(img):
    #using canny to get edges
    return cv2.Canny(grayscale(img), 50, 120)


rightSlope, leftSlope, rightIntercept, leftIntercept = [],[],[],[]
def draw_lines(img, lines, thickness=5):
    global rightSlope, leftSlope, rightIntercept, leftIntercept

    rightColor=[0,255,0]
    leftColor=[255,0,0]
    
    #this is used to filter out the outlying lines that can affect the average
    #We then use the slope we determined to find the y-intercept of the filtered lines by solving for b in y=mx+b
    if lines is not None: 
        for line in lines:
            for x1,y1,x2,y2 in line:
                slope = (y1-y2)/(x1-x2)
                if slope > 0.3:
                    if x1 > 500 :
                        yintercept = y2 - (slope*x2)                    
                        rightSlope.append(slope)
                        rightIntercept.append(yintercept)
                    else: None                
                elif slope < -0.3:
                    if x1 < 600:
                        yintercept = y2 - (slope*x2)                    
                        leftSlope.append(slope)
                        leftIntercept.append(yintercept)    
    else:
        hello = 0
                    
                    
    #We use slicing operators and np.mean() to find the averages of the 30 previous frames
    #This makes the lines more stable, and less likely to glitch
    leftavgSlope = np.mean(leftSlope[-30:])
    leftavgIntercept = np.mean(leftIntercept[-30:])
    
    rightavgSlope = np.mean(rightSlope[-30:])
    rightavgIntercept = np.mean(rightIntercept[-30:])
    
    left_line_x1 = None 
    right_line_x1 = None
    #plotting the lines
    try:
        left_line_x1 = int((0.65*img.shape[0] - leftavgIntercept)/leftavgSlope)
        left_line_x2 = int((img.shape[0] - leftavgIntercept)/leftavgSlope)
    
        right_line_x1 = int((0.65*img.shape[0] - rightavgIntercept)/rightavgSlope)
        right_line_x2 = int((img.shape[0] - rightavgIntercept)/rightavgSlope)

        pts = np.array([[left_line_x1, int(0.65*img.shape[0])],[left_line_x2, int(img.shape[0])],[right_line_x2, int(img.shape[0])],[right_line_x1, int(0.65*img.shape[0])]], np.int32)
        pts = pts.reshape((-1,1,2))
        cv2.fillPoly(img,[pts],(0,0,255))      
        
        
        cv2.line(img, (left_line_x1, int(0.65*img.shape[0])), (left_line_x2, int(img.shape[0])), leftColor, 10)
        cv2.line(img, (right_line_x1, int(0.65*img.shape[0])), (right_line_x2, int(img.shape[0])), rightColor, 10)
    except ValueError:
            #I keep getting errors for some reason, so I put this here. Idk if the error still persists.
        pass

    return [left_line_x1, right_line_x1]
    
    
    
                
def hough_lines(img, rho, theta, threshold, min_line_len, max_line_gap):
    """
    `img` should be the output of a Canny transform.
    """
    #using hough to get the lines from the canny image
    lines = cv2.HoughLinesP(img, rho, theta, threshold, np.array([]), minLineLength=min_line_len, maxLineGap=max_line_gap)
    line_img = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
    coors = draw_lines(line_img, lines)
    #line_img2 = cv2.circle(line_img, (coors[0], 400), radius=10, color=(255, 255, 255), thickness=-6)
    #line_img2 = cv2.circle(line_img2, (coors[1], 400), radius=10, color=(255, 255, 255), thickness=-6)
    direction = "up"
    if coors[0] is not None and coors[1] is not None: 
        left_diff = int(coors[0])
        right_diff = 635-int(coors[1])
        padding = 20
        if (right_diff -padding < left_diff) and (left_diff < right_diff + padding):
            print("stay straight")
            direction = "up"
        elif (left_diff < right_diff - padding) :
            print("move left")
            direction = "left"
        elif (left_diff > right_diff + padding): 
            print("move right")
            direction = "right"
    initialTime = time.time_ns()
    initialTime = sendMotorCommand(motorObj, direction, initialTime)
    
    return line_img


def linedetect(img):
    return hough_lines(img, 1, np.pi/180, 10, 20, 100).first


def processImage(image):
    #function to combine all previous functions
    interest = roi(image)
    
    filterimg = color_filter(interest)
    canny = cv2.Canny(grayscale(filterimg), 50, 120)
    myline = hough_lines(canny, 1, np.pi/180, 10, 20, 5)
    
    weighted_img = cv2.addWeighted(myline, 1, image, 0.8, 0)
    cv2.imshow("img", weighted_img)


    ''' motorObj = MotorController('COM4')
    initialTime = time.time_ns()
    initialTime = sendMotorCommand(motorObj, command, initialTime)'''
    
    return weighted_img

def sendMotorCommand(motorObj, command, lastCommandTime):
    if (time.time_ns() > lastCommandTime + (ONE_SECOND_DELAY*0.1)):
            lastCommandTime = time.time_ns()
            if (command == "up"):
                print("Going Forward")
                motorObj.forward(ROBOT_SPEED)
            elif (command == "down"):
                print("Going Backwards")
                motorObj.backward(ROBOT_SPEED)
            elif (command == "left"):
                print("Going Left")
                motorObj.turnLeft(ROBOT_SPEED*2)
            elif (command == "right"):
                print("Going Right")
                motorObj.turnRight(ROBOT_SPEED*2)
            elif (command == "stop"):
                print("Stopping")
                motorObj.stop()
    return lastCommandTime


cap = cv2.VideoCapture(0) #use cv2.VideoCapture(0) to access camera
while(cap.isOpened()):
     _, frame = cap.read()
     final = processImage(frame)
     #cv2.imshow("final", final)
     if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
