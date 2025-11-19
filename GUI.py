import tkinter as tk
from tkinter import messagebox
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading
import time
import os
import Database.database as db
import orchestrator


class SASPGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MiniShazam 🎧")
        self.root.geometry("720x680")
        self.root.configure(bg="#FAFAFA")

        # Recording state
        self.is_recording = False
        self.record_thread = None
        self.fs = 44100
        self.duration = 20  # default duration (max)
        self.db_connection = db.get_db_connection()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_widgets()

    def create_widgets(self):
        # Title
        tk.Label(
            self.root,
            text="🎵 MiniShazam",
            font=("Helvetica", 22, "bold"),
            bg="#FAFAFA",
            fg="#222"
        ).pack(pady=(25, 10))

        # Microphone icon
        self.mic_label = tk.Label(
            self.root,
            text="🎙",
            font=("Arial", 64),
            bg="#FAFAFA",
            fg="#555"
        )
        self.mic_label.pack(pady=10)

        # Buttons
        frame = tk.Frame(self.root, bg="#FAFAFA")
        frame.pack(pady=15)

        self.record_button = tk.Button(
            frame,
            text="🎙 Tap to minishazam",
            command=self.toggle_recording,
            width=22,
            height=3,
            bg="#FFD966",
            fg="#111",
            relief="raised",
            font=("Helvetica", 12, "bold")
        )
        self.record_button.grid(row=0, column=0, padx=8)

        self.stop_button = tk.Button(
            frame,
            text="⏹ Stop",
            command=self.stop_recording,
            width=12,
            height=2,
            bg="#FF9999",
            fg="#111",
            relief="raised",
            font=("Helvetica", 11, "bold"),
            state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=8)

        self.quit_button = tk.Button(
            self.root,
            text="❌ Quit",
            command=self.on_close,
            width=12,
            height=2,
            bg="#D9D9D9",
            fg="#111",
            font=("Helvetica", 11, "bold")
        )
        self.quit_button.pack(pady=(5, 10))

        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Ready.",
            font=("Arial", 12, "italic"),
            fg="#0077CC",
            bg="#FAFAFA"
        )
        self.status_label.pack(pady=5)

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.record_button.config(text="⏺ Recording...", bg="#FF6B6B", state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.mic_label.config(fg="red")
        self.status_label.config(text="Listening for music")

        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.start()

    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.status_label.config(text="Recording stopped. Saving file...")
            self.mic_label.config(fg="#555")
            self.stop_button.config(state=tk.DISABLED)
            self.record_button.config(text="🎙 Record", bg="#FFD966", state=tk.NORMAL)

    def _record_audio(self):
        try:
            # Ensure directory exists
            save_dir = "music/snippet"
            os.makedirs(save_dir, exist_ok=True)

            # Unique filename with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(save_dir, f"recording_{timestamp}.wav")

            # Record
            recording = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=1, dtype='float64')
            for _ in range(int(self.duration * 10)):
                if not self.is_recording:
                    break
                time.sleep(0.1)
            sd.stop()
            sd.wait()

            if len(recording) > 0:
                wav.write(save_path, self.fs, recording)
                self.status_label.config(text=f"Saved to {save_path}")

                self.status_label.config(text="Identifying snippet...")
                matches = orchestrator.find_matching_track(self.db_connection, save_path)
                if matches:
                    best_match = matches[0]
                    self.status_label.config(text=f"Match: {best_match} 🎶")
                    messagebox.showinfo("Match Found", f"Best match: {best_match}")
                else:
                    self.status_label.config(text="No match found ❌")
                    messagebox.showinfo("No Match", "Could not identify the recording.")
            else:
                self.status_label.config(text="Recording failed ❌")

        except Exception as e:
            messagebox.showerror("Recording Error", str(e))
        finally:
            self.is_recording = False
            self.stop_button.config(state=tk.DISABLED)
            self.record_button.config(text="🎙 Record", bg="#FFD966", state=tk.NORMAL)
            self.mic_label.config(fg="#555")

    def on_close(self):
        try:
            if self.record_thread and self.record_thread.is_alive():
                self.is_recording = False
                self.record_thread.join(timeout=1)
            if self.db_connection:
                self.db_connection.close()
        finally:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SASPGUI(root)
    root.mainloop()
