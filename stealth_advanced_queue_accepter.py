#!/usr/bin/env python3
import os
import sys
import threading
import time
import json
import random
import ctypes
import logging

import cv2
import numpy as np
import pyautogui
import winsound
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# — Determine script directory —
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# — Logging setup —
LOG_FILE = os.path.join(SCRIPT_DIR, "queue_accept.log")
logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info("=== Starting Queue Accepter GUI ===")

# — Load configuration —
cfg_path = os.path.join(SCRIPT_DIR, "config.json")
if not os.path.exists(cfg_path):
    messagebox.showerror("Error", f"Missing config.json at {cfg_path}")
    sys.exit(1)
with open(cfg_path, "r") as f:
    cfg = json.load(f)
WEBHOOK_URL = cfg.get("discord_webhook_url", "").strip()
USER_ID     = cfg.get("discord_user_id", "").strip()

# — Helper: Discord notification —
def notify_discord(message: str):
    if not WEBHOOK_URL or not USER_ID:
        return
    payload = {"content": f"<@{USER_ID}> {message}"}
    try:
        resp = requests.post(WEBHOOK_URL, json=payload, timeout=5)
        resp.raise_for_status()
    except Exception as e:
        logging.error(f"Discord notify failed: {e}")

# — Win32 SendInput for clicks —
PUL = ctypes.POINTER(ctypes.c_ulong)
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]
class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]

def send_click():
    for flag in (0x0002, 0x0004):
        inp = INPUT(ctypes.c_ulong(0),
            MOUSEINPUT(0,0,0,flag,0,ctypes.pointer(ctypes.c_ulong(0))))
        ctypes.windll.user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))

def human_click(cx, cy, w, h):
    time.sleep(random.uniform(0.15,0.3))
    tx = cx + random.uniform(-0.15,0.15)*w
    ty = cy + random.uniform(-0.15,0.15)*h
    pyautogui.moveTo(tx, ty, duration=random.uniform(0.2,0.45),
                     tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.05,0.12))
    send_click()

# — Detection thread —
class Accepter(threading.Thread):
    def __init__(self, cfg, gui):
        super().__init__(daemon=True)
        self.cfg, self.gui = cfg, gui
        self.running = threading.Event()
        self.stop    = threading.Event()
        self.debug_img = None

        # ORB + BF setup
        self.orb = cv2.ORB_create(300)
        self.bf  = cv2.BFMatcher(cv2.NORM_HAMMING)

        # load templates
        tpl_dir = os.path.join(SCRIPT_DIR, cfg["templates_folder"])
        self.templates = []
        for fn in os.listdir(tpl_dir):
            img = cv2.imread(os.path.join(tpl_dir, fn), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            kp, des = self.orb.detectAndCompute(img, None)
            if des is None:
                continue
            self.templates.append((img, kp, des))
        if not self.templates:
            messagebox.showerror("Error", f"No templates in {tpl_dir}")
            sys.exit(1)

        # initialize ROI
        sw, sh = pyautogui.size()
        x, y, w, h = cfg["raw_roi"]
        self.x0, self.y0 = int(x*sw), int(y*sh)
        self.w0, self.h0 = int(w*sw), int(h*sh)

    def run(self):
        while not self.stop.is_set():
            if not self.running.is_set():
                time.sleep(0.1)
                continue

            try:
                shot = pyautogui.screenshot(region=(self.x0, self.y0, self.w0, self.h0))
            except Exception as e:
                logging.error(f"Screenshot failed: {e}")
                time.sleep(1)
                continue

            if shot is None or shot.size[0] == 0 or shot.size[1] == 0:
                logging.warning("Empty screenshot; check ROI.")
                time.sleep(1)
                continue

            frame = cv2.cvtColor(np.array(shot), cv2.COLOR_BGR2RGB)
            gray  = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            fkp, fdes = self.orb.detectAndCompute(gray, None)

            best, clicked, match_info = 0, False, None
            if fdes is not None:
                for tpl_img, tkp, tdes in self.templates:
                    matches = self.bf.knnMatch(tdes, fdes, k=2)
                    good    = [m for m,n in matches if m.distance < 0.75*n.distance]
                    cnt     = len(good)
                    best    = max(best, cnt)
                    if cnt < self.cfg["min_matches"]:
                        continue

                    # homography + click
                    src = np.float32([tkp[m.queryIdx].pt for m in good]).reshape(-1,1,2)
                    dst = np.float32([fkp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
                    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                    if H is None:
                        continue

                    h_img, w_img = tpl_img.shape
                    pts = cv2.perspectiveTransform(
                        np.float32([[0,0],[w_img,0],[w_img,h_img],[0,h_img]]).reshape(-1,1,2), H
                    )
                    cx = int(pts[:,0,0].mean()) + self.x0
                    cy = int(pts[:,0,1].mean()) + self.y0

                    human_click(cx, cy, w_img, h_img)
                    if self.gui.sound_var.get():
                        winsound.Beep(800, 150)

                    logging.info(f"Click at {cx},{cy} ({cnt} matches)")
                    if self.gui.notify_var.get():
                        notify_discord("A queue popped! 🎉 Clicked.")

                    clicked = True
                    match_info = (tpl_img, tkp, good, gray)
                    break

            self.gui.status_var.set(f"Current matches: {best}")

            # debug display
            if self.gui.debug_var.get():
                if match_info:
                    tpl_img, tkp, good, gray = match_info
                    disp = cv2.drawMatches(
                        tpl_img, tkp,
                        cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), fkp,
                        good, None,
                        matchColor=(0,255,0),
                        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS
                    )
                else:
                    disp = frame
                self.debug_img = cv2.resize(disp, (self.w0, self.h0))

            # fire the GUI update
            self.gui.window.event_generate("<<DEBUG>>", when="tail")
            time.sleep(random.uniform(3,6) if clicked else 0.2)

# — GUI app —
class App:
    def __init__(self, root):
        root.title("Queue Accepter")
        self.window = root                # <— store for event_generate()
        self.cfg = cfg

        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="x")

        ttk.Button(frm, text="Select ROI", command=self.select_roi).grid(row=0, column=0)
        self.debug_var = tk.BooleanVar()
        ttk.Checkbutton(frm, text="Debug", variable=self.debug_var, command=self.toggle_debug).grid(row=0, column=1)
        self.sound_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Sound", variable=self.sound_var).grid(row=0, column=2)
        self.notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Notify", variable=self.notify_var).grid(row=0, column=3)

        ttk.Label(frm, text="Min matches:").grid(row=1, column=0)
        self.slider = ttk.Scale(frm, from_=5, to=100, orient="horizontal")
        self.slider.grid(row=1, column=1, columnspan=2, sticky="we")
        self.min_label = ttk.Label(frm, text=str(self.cfg["min_matches"]))
        self.min_label.grid(row=1, column=3)
        self.slider.config(command=self.on_slider)
        self.slider.set(self.cfg["min_matches"])

        self.status_var = tk.StringVar(value="Current matches: 0")
        ttk.Label(frm, textvariable=self.status_var).grid(row=2, column=0, columnspan=4, pady=(5,0))

        btnf = ttk.Frame(root, padding=10)
        btnf.pack()
        self.start_btn = ttk.Button(btnf, text="Start", command=self.start)
        self.start_btn.grid(row=0, column=0, padx=5)
        self.pause_btn = ttk.Button(btnf, text="Pause", command=self.pause, state="disabled")
        self.pause_btn.grid(row=0, column=1, padx=5)
        ttk.Button(btnf, text="Quit", command=self.quit).grid(row=0, column=2, padx=5)

        # prepare debug canvas and show immediately if flag is on
        self.canvas = tk.Canvas(root, bg="black")
        if self.debug_var.get():
            self.canvas.pack(padx=10, pady=5)
        root.bind("<<DEBUG>>", self.update_debug)

        self.worker = Accepter(self.cfg, self)
        self.worker.start()

    def toggle_debug(self):
        if self.debug_var.get():
            self.canvas.pack(padx=10, pady=5)
        else:
            self.canvas.pack_forget()

    def select_roi(self):
        messagebox.showinfo("ROI Selection", "Draw region then press ENTER/SPACE to confirm.")
        full = pyautogui.screenshot()
        arr = cv2.cvtColor(np.array(full), cv2.COLOR_BGR2RGB)
        px, py, pw, ph = map(int, cv2.selectROI("Draw ROI", arr, False, False))
        cv2.destroyWindow("Draw ROI")
        sw, sh = full.size
        self.cfg["raw_roi"] = [px/sw, py/sh, pw/sw, ph/sh]
        with open(os.path.join(SCRIPT_DIR, "config.json"), "w") as f:
            json.dump(self.cfg, f, indent=2)
        # apply immediately
        self.worker.x0, self.worker.y0, self.worker.w0, self.worker.h0 = px, py, pw, ph
        messagebox.showinfo("ROI Saved", f"Region set to {px},{py},{pw},{ph}")

    def on_slider(self, val):
        v = int(float(val))
        self.cfg["min_matches"] = v
        self.min_label.config(text=str(v))
        with open(os.path.join(SCRIPT_DIR, "config.json"), "w") as f:
            json.dump(self.cfg, f, indent=2)

    def start(self):
        self.worker.running.set()
        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        # no longer unchecking Debug here

    def pause(self):
        self.worker.running.clear()
        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled")

    def quit(self):
        self.worker.stop.set()
        self.window.destroy()

    def update_debug(self, event):
        img = self.worker.debug_img
        if img is None:
            return
        im = Image.fromarray(img)
        imgtk = ImageTk.PhotoImage(im)
        self.canvas.config(width=img.shape[1], height=img.shape[0])
        self.canvas.create_image(0, 0, anchor="nw", image=imgtk)
        self.canvas.image = imgtk  # keep reference

if __name__ == "__main__":
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    App(root)
    root.mainloop()
