import os
import time
import keyboard
import datetime
import cv2
import tkinter as tk
import numpy as np
from mss import mss
from mouse import get_position as get_mouse_position
import threading
import win32gui
import win32ui
import win32con

class TranslucentWindow(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.start_x = None
        self.start_y = None
        self.current_x = None
        self.current_y = None
        self.rect = None
        self.countdown_text = None
        self.canvas = None
        self.recording = False
        self.f8_pressed = False
        self.thread_running = False
        self.mouse_released = False

    def start_recording_button(self):
        self.master.withdraw() # hide root window
        self.deiconify() # bring TranslucentWindow to front
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.5)
        self.attributes('-topmost', True)    
        self.wm_attributes('-transparentcolor', 'gray')

        # reset canvas
        if self.canvas:
            self.canvas.delete('all')
            self.canvas.pack_forget()

        # create new canvas with black background
        self.canvas = tk.Canvas(self, bg='black', bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # bind button actions to functions for those buttons
        self.canvas.bind('<Button-1>', self.on_left_click)
        self.canvas.bind('<B1-Motion>', self.on_mouse_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_left_release)

        # clean up  variables
        self.start_x = None
        self.start_y = None
        self.rect = None
    
        
    def check_f8_pressed(self):
        while not self.recording and not self.f8_pressed and self.mouse_released:

            if keyboard.is_pressed('F8'):
                self.f8_pressed = True

                # set current mouse x,y position to end position variables
                end_x = self.current_x
                end_y = self.current_y

                # create variables for window dimensions
                x, y, width, height = min(self.start_x, end_x), min(self.start_y, end_y), abs(self.start_x - end_x), abs(self.start_y - end_y) 
                
                self.begin_recording(x, y, width, height, end_x, end_y)
            
            elif keyboard.is_pressed('esc'):
                self.stop_recording()

            time.sleep(0.01)

        self.thread_running = False

    def stop_recording(self):
        self.mouse_released = False
        self.f8_pressed = False
        self.recording = False
        self.withdraw()
        self.master.deiconify()
        self.master.wm_attributes("-topmost", True)
        self.master.wm_attributes("-topmost", False)

    def view_recording(self):
        folder_name = "recordings"
        path = os.path.abspath(folder_name)
        os.startfile(path)

    def on_left_click(self, event):
        self.mouse_released = False

        if not self.recording and not self.rect:
            self.start_x = self.winfo_rootx() + event.x
            self.start_y = self.winfo_rooty() + event.y
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='white', width=2)
        elif not self.recording and self.rect:
            self.canvas.delete(self.rect)
            self.start_x = self.winfo_rootx() + event.x
            self.start_y = self.winfo_rooty() + event.y
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='white', width=2)

    def on_mouse_drag(self, event):
        self.mouse_released = False

        if not self.recording and self.rect:
            self.canvas.delete(self.rect)
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, event.x, event.y, outline='white', width=2, fill='gray')
        
    def on_left_release(self, event):
        self.mouse_released = True

        if not self.recording and self.rect:
            # change for rectangle
            self.canvas.itemconfig(self.rect, outline='blue')

            # set final mouse position coords
            self.current_x = event.x
            self.current_y = event.y

            # if thread is not running and not recording, run thread to check f8 key presses
            if not self.thread_running:
                self.thread_running = True
                t = threading.Thread(target=self.check_f8_pressed)
                t.start()

    def begin_recording(self, x, y, width, height, end_x, end_y):
        if not self.recording:
            # set recording boolean to disable more rectangles
            self.recording = True

            # get center of red rectangle
            x_center = (self.start_x + end_x) // 2
            y_center = (self.start_y + end_y) // 2

            # Add a 3 second countdown, create and destroy text each loop
            for i in range(3, 0, -1):
                self.countdown_text = self.canvas.create_text(x_center, y_center, text=f"{i}", font=('Helvetica', 36, 'bold'), fill='white', tags='countdown')
                self.update()
                time.sleep(1)
                self.canvas.delete('countdown')

            self.update()

            self.wm_attributes('-transparentcolor', 'gray')
            self.canvas.configure(background='gray')
            self.canvas.itemconfig(self.rect, outline='red')
            self.update()

            self.record_screen(x, y, width, height)

    def record_screen(self, x, y, width, height):
        border_width = 2
        x += border_width
        y += border_width
        width -= border_width * 2
        height -= border_width * 2

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        current_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f'recordings/recording_{current_time}.mp4'
        out = cv2.VideoWriter(filename, fourcc, 60.0, (width, height))
        sct = mss()

        def get_cursor_mask(cursor_size=5):
            cursor_mask = np.zeros((cursor_size, cursor_size, 3), dtype=np.uint8)
            cursor_mask = cv2.circle(cursor_mask, (cursor_size // 2, cursor_size // 2), cursor_size // 2, (255, 255, 255), -1)
            return cursor_mask

        cursor_mask = get_cursor_mask()

        while True:
            hwnd = win32gui.GetDesktopWindow()
            hwindc = win32gui.GetWindowDC(hwnd)
            srcdc = win32ui.CreateDCFromHandle(hwindc)
            memdc = srcdc.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(srcdc, width, height)
            memdc.SelectObject(bmp)
            memdc.BitBlt((0, 0), (width, height), srcdc, (x, y), win32con.SRCCOPY)

            bmpinfo = bmp.GetInfo()
            bmpstr = bmp.GetBitmapBits(True)

            img = np.frombuffer(bmpstr, dtype='uint8')
            img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)

            srcdc.DeleteDC()
            memdc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwindc)
            win32gui.DeleteObject(bmp.GetHandle())

            frame = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

            # draw the mouse cursor on the frame
            mx, my = get_mouse_position()
            if x <= mx < x + width and y <= my < y + height:
                cursor_x, cursor_y = mx - x, my - y
                roi_start_y, roi_end_y = cursor_y, min(cursor_y + cursor_mask.shape[0], height)
                roi_start_x, roi_end_x = cursor_x, min(cursor_x + cursor_mask.shape[1], width)
                frame_roi = frame[roi_start_y:roi_end_y, roi_start_x:roi_end_x]

                # Crop the cursor_mask to match the dimensions of the frame's ROI
                cursor_mask_cropped = cursor_mask[:roi_end_y - roi_start_y, :roi_end_x - roi_start_x]
                frame_roi = cv2.addWeighted(frame_roi, 1, cursor_mask_cropped, 0.7, 0)
                frame[roi_start_y:roi_end_y, roi_start_x:roi_end_x] = frame_roi

            # Write the cropped frame to the output file
            out.write(frame)

            # stop recording and save the video when F8 is pressed
            if keyboard.is_pressed('F8'):
                out.release()
                self.stop_recording()
                break
        

def main():
    root = tk.Tk()
    root.title("SnipRecorder")
    root.resizable(False, False)

    # Get the screen dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Set the window size
    window_width = 250
    window_height = 185

    # Calculate the x and y coordinates to center the window
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2

    # Set the window position
    root.geometry(f"{window_width}x{window_height}+{x}+{int(y/1.5)}")

    app = TranslucentWindow(master=root)
    app.withdraw()

    # label for information on how to operate the program
    instruction_label = tk.Label(root,
                                 text="When you have selected your desired recording size, toggle F8 to Start/Stop.",
                                 wraplength=230,  # Set the maximum width of the label before wrapping the text
                                 justify=tk.CENTER)  # Center the text
    instruction_label.place(x=15, y=10)    
    
    # start button to begin selecting area
    start_button = tk.Button(root, 
                             text="Select Area",
                             width=30,
                             height=3,
                             command=app.start_recording_button)
    start_button.place(x=15, y=50)
    
    # view recording button allows user to view where recordings are stored
    view_button = tk.Button(root, 
                            text="View Recordings", 
                            width=30,
                            height=3,
                            command=app.view_recording,)
    view_button.place(x=15, y=110)

    # root.withdraw()
    root.mainloop()

if __name__ == '__main__':
    main()
