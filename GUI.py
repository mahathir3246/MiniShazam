"""
MiniShazam Graphical User Interface (GUI)

This file creates a simple desktop application window where you can:
1. Click a button to start recording from your microphone
2. Click stop when you're done
3. See the matching song name displayed

The GUI uses Tkinter, which comes built into Python - no extra install needed.

HOW TO USE:
1. Run: python3 GUI.py
2. Click "Tap to minishazam" button
3. Play a song near your microphone
4. Click "Stop" when ready
5. Wait for the result - it will show which song matched!

IMPORTANT: Make sure you've already built the database using:
    python3 cli.py build
"""

import tkinter as tk
from tkinter import messagebox
import sounddevice as sd      # For recording from microphone
import numpy as np            # For handling audio data arrays
import scipy.io.wavfile as wav # For saving audio to WAV files
import threading              # For running recording in background
import time                   # For timestamps and delays
import os                     # For file/folder operations
import Database.database as db
import orchestrator


class SASPGUI:
    """
    The main GUI application class.
    
    This class creates the window, buttons, labels, and handles
    all the user interactions like starting/stopping recordings.
    """
    
    def __init__(self, root):
        """
        Initialize the GUI application.
        
        Args:
            root: The main Tkinter window object
        """
        self.root = root
        self.root.title("MiniShazam 🎧")      # Window title
        self.root.geometry("720x680")          # Window size (width x height)
        self.root.configure(bg="#FAFAFA")      # Light gray background color

        # ========================================
        # Recording State Variables
        # ========================================
        self.is_recording = False    # Are we currently recording?
        self.record_thread = None    # Background thread for recording
        self.fs = 44100              # Sample rate (44.1kHz - CD quality)
        self.duration = 20           # Maximum recording duration in seconds
        
        # Connect to the database once when the app starts
        # This connection stays open while the app is running
        self.db_connection = db.get_db_connection()
        
        # Set up what happens when user closes the window
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Create all the visual elements (buttons, labels, etc.)
        self.create_widgets()

    def create_widgets(self):
        """
        Creates all the visual elements in the window.
        
        Layout from top to bottom:
        1. Title label ("MiniShazam")
        2. Big microphone emoji icon
        3. Record and Stop buttons side by side
        4. Quit button
        5. Status label showing current state
        """
        
        # ========================================
        # Title at the top
        # ========================================
        tk.Label(
            self.root,
            text="🎵 MiniShazam",
            font=("Helvetica", 22, "bold"),
            bg="#FAFAFA",
            fg="#222"
        ).pack(pady=(25, 10))  # Padding: 25px above, 10px below

        # ========================================
        # Big microphone icon in the middle
        # ========================================
        self.mic_label = tk.Label(
            self.root,
            text="🎙",
            font=("Arial", 64),
            bg="#FAFAFA",
            fg="#555"  # Gray when not recording, red when recording
        )
        self.mic_label.pack(pady=10)

        # ========================================
        # Button container frame
        # ========================================
        frame = tk.Frame(self.root, bg="#FAFAFA")
        frame.pack(pady=15)

        # Record button - starts/toggles recording
        self.record_button = tk.Button(
            frame,
            text="🎙 Tap to minishazam",
            command=self.toggle_recording,  # Called when button is clicked
            width=22,
            height=3,
            bg="#FFD966",       # Yellow background
            fg="#111",          # Dark text
            relief="raised",    # 3D raised effect
            font=("Helvetica", 12, "bold")
        )
        self.record_button.grid(row=0, column=0, padx=8)

        # Stop button - stops recording early
        self.stop_button = tk.Button(
            frame,
            text="⏹ Stop",
            command=self.stop_recording,
            width=12,
            height=2,
            bg="#FF9999",       # Light red background
            fg="#111",
            relief="raised",
            font=("Helvetica", 11, "bold"),
            state=tk.DISABLED   # Disabled until recording starts
        )
        self.stop_button.grid(row=0, column=1, padx=8)

        # ========================================
        # Quit button
        # ========================================
        self.quit_button = tk.Button(
            self.root,
            text="❌ Quit",
            command=self.on_close,  # Same as clicking the X button
            width=12,
            height=2,
            bg="#D9D9D9",       # Gray background
            fg="#111",
            font=("Helvetica", 11, "bold")
        )
        self.quit_button.pack(pady=(5, 10))

        # ========================================
        # Status label at the bottom
        # Shows current state and results
        # ========================================
        self.status_label = tk.Label(
            self.root,
            text="Ready.",
            font=("Arial", 12, "italic"),
            fg="#0077CC",       # Blue text
            bg="#FAFAFA"
        )
        self.status_label.pack(pady=5)

    def toggle_recording(self):
        """
        Called when the record button is clicked.
        If not recording, starts recording. If recording, stops it.
        """
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """
        Begins recording audio from the microphone.
        
        Changes the UI to show recording state (red icon, disabled button)
        and starts a background thread to capture audio without freezing the UI.
        """
        self.is_recording = True
        
        # Update button appearance to show we're recording
        self.record_button.config(text="⏺ Recording...", bg="#FF6B6B", state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)  # Enable stop button
        self.mic_label.config(fg="red")           # Make mic icon red
        self.status_label.config(text="Listening for music")

        # Start recording in a background thread
        # This prevents the UI from freezing while we record
        self.record_thread = threading.Thread(target=self._record_audio)
        self.record_thread.start()

    def stop_recording(self):
        """
        Stops the current recording.
        
        Sets the is_recording flag to False, which the recording thread
        checks periodically. The thread will then stop and process the audio.
        """
        if self.is_recording:
            self.is_recording = False
            self.status_label.config(text="Recording stopped. Saving file...")
            self.mic_label.config(fg="#555")      # Make mic icon gray again
            self.stop_button.config(state=tk.DISABLED)
            self.record_button.config(text="🎙 Record", bg="#FFD966", state=tk.NORMAL)

    def _record_audio(self):
        """
        Internal method that runs in a background thread.
        
        This does the actual work of:
        1. Recording audio from the microphone
        2. Saving it to a WAV file
        3. Running the matching algorithm
        4. Showing the result to the user
        
        It runs in a separate thread so the UI stays responsive.
        """
        try:
            # Make sure the save directory exists
            save_dir = "music/snippet"
            os.makedirs(save_dir, exist_ok=True)

            # Create a unique filename with timestamp
            # Example: recording_20231215_143022.wav
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(save_dir, f"recording_{timestamp}.wav")

            # Start recording from the microphone
            # sd.rec() returns immediately and records in the background
            # Parameters:
            #   - Number of samples to record (duration * sample rate)
            #   - Sample rate (44100 Hz = CD quality)
            #   - Channels (1 = mono, 2 = stereo)
            #   - Data type (float64 for high precision)
            recording = sd.rec(int(self.duration * self.fs), samplerate=self.fs, channels=1, dtype='float64')
            
            # Wait for recording to finish OR for user to press Stop
            # Check every 0.1 seconds if we should stop early
            for _ in range(int(self.duration * 10)):
                if not self.is_recording:
                    break
                time.sleep(0.1)
            
            # Stop recording
            sd.stop()
            sd.wait()  # Wait for any remaining audio to be processed

            # Save the recording to a WAV file
            if len(recording) > 0:
                wav.write(save_path, self.fs, recording)
                self.status_label.config(text=f"Saved to {save_path}")

                # Now try to identify which song it is
                self.status_label.config(text="Identifying snippet...")
                
                # This is where the magic happens!
                # find_matching_track compares our recording against the database
                matches = orchestrator.find_matching_track(self.db_connection, save_path)
                
                if matches:
                    # We found a match! Show the best result
                    best_match = matches[0]
                    self.status_label.config(text=f"Match: {best_match} 🎶")
                    messagebox.showinfo("Match Found", f"Best match: {best_match}")
                else:
                    # No match found - song might not be in database
                    self.status_label.config(text="No match found ❌")
                    messagebox.showinfo("No Match", "Could not identify the recording.")
            else:
                self.status_label.config(text="Recording failed ❌")

        except Exception as e:
            # Show any errors to the user
            messagebox.showerror("Recording Error", str(e))
        finally:
            # Always reset the UI state when done
            self.is_recording = False
            self.stop_button.config(state=tk.DISABLED)
            self.record_button.config(text="🎙 Record", bg="#FFD966", state=tk.NORMAL)
            self.mic_label.config(fg="#555")

    def on_close(self):
        """
        Called when the user closes the window (X button or Quit button).
        
        Properly cleans up:
        1. Stops any active recording
        2. Closes the database connection
        3. Destroys the window
        """
        try:
            # If recording is still running, stop it
            if self.record_thread and self.record_thread.is_alive():
                self.is_recording = False
                self.record_thread.join(timeout=1)  # Wait up to 1 second
            
            # Close database connection
            if self.db_connection:
                self.db_connection.close()
        finally:
            # Close the window
            self.root.destroy()


# ========================================
# Application Entry Point
# ========================================
# This code runs when you execute: python3 GUI.py
if __name__ == "__main__":
    # Create the main window
    root = tk.Tk()
    
    # Create our application
    app = SASPGUI(root)
    
    # Start the GUI event loop (keeps window open and responsive)
    root.mainloop()
