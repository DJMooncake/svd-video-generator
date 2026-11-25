import contextlib
import queue
import sys
import threading
import time
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import imageio.v2 as imageio
from PIL import Image, ImageTk

from engine import COMPONENTS, OUTPUT, generate
from setup_model import download_model, missing_files


THEMES = {
    "dark": {
        "background": "#1c1d20", "panel": "#24262a", "field": "#303238",
        "text": "#e6e8eb", "muted": "#a7adb7", "button": "#373b42",
        "accent": "#637da9", "video": "#111214", "log": "#111214",
    },
    "light": {
        "background": "#eef0f3", "panel": "#ffffff", "field": "#f1f3f6",
        "text": "#20232a", "muted": "#59616d", "button": "#dfe3e9",
        "accent": "#46638d", "video": "#161719", "log": "#ffffff",
    },
}


class LogStream:
    def __init__(self, original, events):
        self.original = original
        self.events = events
        self.pending = ""

    def write(self, text):
        if self.original is not None:
            self.original.write(text)
        self.pending += text.replace("\r", "\n")
        lines = self.pending.split("\n")
        self.pending = lines.pop()
        for line in lines:
            if line.strip():
                self.events.put(("log", line))
        return len(text)

    def flush(self):
        if self.original is not None:
            self.original.flush()

    def finish(self):
        if self.pending.strip():
            self.events.put(("log", self.pending))
        self.pending = ""
        self.flush()

    def isatty(self):
        return False


class VideoGeneratorV2:
    def __init__(self, root):
        self.root = root
        root.title("SVD Video Generator v3")
        root.geometry("1200x760")
        root.minsize(900, 600)
        self.events = queue.Queue()
        self.running = False
        self.reader = None
        self.video_path = None
        self.after_id = None
        self.playing = False
        self.frame_image = None
        self.current_frame = None
        self.theme_widgets = []

        self.image = tk.StringVar()
        self.output = tk.StringVar(value=str(OUTPUT))
        self.frames = tk.StringVar(value="25")
        self.steps = tk.StringVar(value="25")
        self.fps = tk.StringVar(value="6")
        self.seed = tk.StringVar(value="42")
        self.status = tk.StringVar(value="Choose an image to begin. Runs offline.")
        self.dark = tk.BooleanVar(value=True)

        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self.register(root, "background")
        sidebar = self.register(tk.Frame(root, padx=16, pady=16, width=310), "panel")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        self.label(sidebar, "SVD Video Generator v3", "heading").grid(row=0, column=0, sticky="w")
        self.label(sidebar, "Powered by Stability AI | Offline", "muted").grid(
            row=1, column=0, sticky="w", pady=(2, 20)
        )
        self.label(sidebar, "Input image").grid(row=2, column=0, sticky="w")
        self.entry(sidebar, self.image).grid(row=3, column=0, sticky="ew", pady=(5, 6))
        self.button(sidebar, "Browse image...", self.choose_image).grid(row=4, column=0, sticky="ew")
        self.label(sidebar, "Save videos to").grid(row=5, column=0, sticky="w", pady=(18, 0))
        self.entry(sidebar, self.output).grid(row=6, column=0, sticky="ew", pady=(5, 6))
        self.button(sidebar, "Browse folder...", self.choose_output).grid(row=7, column=0, sticky="ew")
        self.label(sidebar, "Settings", "heading").grid(row=8, column=0, sticky="w", pady=(20, 6))
        options = self.register(tk.Frame(sidebar), "panel")
        options.grid(row=9, column=0, sticky="ew")
        options.columnconfigure((0, 1), weight=1)
        for index, (name, variable) in enumerate(
            (("Frames", self.frames), ("Steps", self.steps), ("FPS", self.fps), ("Seed", self.seed))
        ):
            row, column = divmod(index, 2)
            self.label(options, name).grid(row=row * 2, column=column, sticky="w", pady=(5, 2))
            self.entry(options, variable, width=11).grid(
                row=row * 2 + 1, column=column, sticky="ew", padx=(0, 8)
            )
        self.label(
            sidebar, "Images are center-cropped to 1024 x 576.\nGeneration can take several minutes.", "muted"
        ).grid(row=10, column=0, sticky="w", pady=16)
        self.generate_button = self.button(sidebar, "Generate video", self.start, accent=True)
        self.generate_button.grid(row=11, column=0, sticky="ew")
        self.theme_toggle = self.register(tk.Checkbutton(
            sidebar, text="Dark mode", variable=self.dark, command=self.apply_theme,
            anchor="w", borderwidth=0, highlightthickness=0
        ), "check")
        self.theme_toggle.grid(row=12, column=0, sticky="w", pady=(15, 0))
        self.setup_button = self.button(sidebar, "Download model...", self.setup_model)
        self.setup_button.grid(row=13, column=0, sticky="ew", pady=(12, 0))

        content = self.register(tk.Frame(root, padx=15, pady=15), "background")
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=4)
        content.rowconfigure(3, weight=1)
        self.viewer = self.register(tk.Label(
            content, text="Your video will play here when it is done.",
            anchor="center", borderwidth=0
        ), "video")
        self.viewer.grid(row=0, column=0, sticky="nsew")
        self.viewer.bind("<Configure>", self.resize_frame)
        controls = self.register(tk.Frame(content), "background")
        controls.grid(row=1, column=0, sticky="ew", pady=(10, 4))
        self.button(controls, "Open video...", self.choose_video).pack(side="left", padx=(0, 8))
        self.play_button = self.button(controls, "Pause", self.toggle_play)
        self.play_button.pack(side="left")
        self.play_button.configure(state="disabled")
        self.label(content, textvariable=self.status, role="muted").grid(
            row=2, column=0, sticky="w", pady=(6, 8)
        )
        log_panel = self.register(tk.Frame(content), "background")
        log_panel.grid(row=3, column=0, sticky="nsew")
        log_panel.columnconfigure(0, weight=1)
        log_panel.rowconfigure(1, weight=1)
        self.label(log_panel, "Live log", "muted").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.log = self.register(tk.Text(
            log_panel, height=5, wrap="word", state="disabled", relief="flat",
            font=("Consolas", 10), padx=8, pady=8
        ), "log")
        self.log.grid(row=1, column=0, sticky="nsew")
        scroll = tk.Scrollbar(log_panel, command=self.log.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)
        self.apply_theme()
        self.append_log("Ready. Select an image and generate a video.")
        if missing_files(COMPONENTS):
            self.status.set("Model not installed. Click Download model...")
            self.append_log("Model not installed. Review the model license and log in before downloading.")
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_id = root.after(100, self.poll)

    def register(self, widget, role):
        self.theme_widgets.append((widget, role))
        return widget

    def label(self, parent, text=None, role="label", **kwargs):
        font = ("Segoe UI", 13, "bold") if role == "heading" else ("Segoe UI", 9)
        return self.register(tk.Label(parent, text=text, font=font, anchor="w", **kwargs), role)

    def entry(self, parent, variable, **kwargs):
        return self.register(tk.Entry(
            parent, textvariable=variable, relief="flat", borderwidth=5, **kwargs
        ), "field")

    def button(self, parent, text, command, accent=False):
        return self.register(tk.Button(
            parent, text=text, command=command, relief="flat", borderwidth=0,
            padx=10, pady=6, font=("Segoe UI", 9), cursor="hand2"
        ), "accent" if accent else "button")

    def apply_theme(self):
        colors = THEMES["dark" if self.dark.get() else "light"]
        for widget, role in self.theme_widgets:
            if role in ("background", "panel"):
                widget.configure(bg=colors[role])
            elif role in ("label", "heading", "muted"):
                parent_bg = widget.master.cget("bg")
                widget.configure(bg=parent_bg, fg=colors["muted" if role == "muted" else "text"])
            elif role == "field":
                widget.configure(bg=colors["field"], fg=colors["text"], insertbackground=colors["text"])
            elif role in ("button", "accent"):
                widget.configure(
                    bg=colors[role], fg="#ffffff" if role == "accent" else colors["text"],
                    activebackground=colors["accent"], activeforeground="#ffffff",
                    disabledforeground=colors["muted"]
                )
            elif role == "check":
                widget.configure(
                    bg=colors["panel"], fg=colors["text"], selectcolor=colors["field"],
                    activebackground=colors["panel"], activeforeground=colors["text"]
                )
            elif role == "video":
                widget.configure(bg=colors["video"], fg="#a7adb7")
            elif role == "log":
                widget.configure(bg=colors["log"], fg=colors["text"], insertbackground=colors["text"])

    def choose_image(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Choose an image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")]
        )
        if path:
            self.image.set(path)

    def choose_output(self):
        path = filedialog.askdirectory(parent=self.root, title="Choose output folder")
        if path:
            self.output.set(path)

    def choose_video(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Open a video", initialdir=self.output.get(),
            filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")]
        )
        if path:
            self.open_video(path)

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", f"[{time.strftime('%H:%M:%S')}] {text}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        if self.running:
            return
        if missing_files(COMPONENTS):
            messagebox.showerror(
                "Model not installed", "Click Download model... and complete setup first.", parent=self.root
            )
            return
        try:
            settings = (int(self.frames.get()), int(self.steps.get()), int(self.fps.get()), int(self.seed.get()))
            if not self.image.get() or not self.output.get():
                raise ValueError("Choose an input image and an output folder.")
            if not Path(self.image.get()).is_file():
                raise ValueError("The chosen input image does not exist.")
            if not (2 <= settings[0] <= 25 and 1 <= settings[1] <= 100
                    and 1 <= settings[2] <= 30 and 0 <= settings[3] <= 2**32 - 1):
                raise ValueError("Frames: 2-25; steps: 1-100; FPS: 1-30; seed: 0-4294967295.")
        except ValueError as exc:
            self.append_log(f"Invalid settings: {exc}")
            messagebox.showerror("Invalid settings", str(exc), parent=self.root)
            return
        input_path, output_path = self.image.get(), self.output.get()
        self.running = True
        self.generate_button.configure(state="disabled")
        self.setup_button.configure(state="disabled")
        self.status.set("Starting...")
        self.append_log(f"Starting generation: {settings[0]} frames, {settings[1]} steps, "
                        f"{settings[2]} FPS, seed {settings[3]}.")

        def worker():
            stdout = LogStream(sys.stdout, self.events)
            stderr = LogStream(sys.stderr, self.events)
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    path = generate(input_path, output_path, *settings,
                                    progress=lambda m: self.events.put(("status", m)))
                stdout.finish()
                stderr.finish()
                self.events.put(("done", str(path)))
            except Exception:
                stdout.finish()
                stderr.finish()
                self.events.put(("error", traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def setup_model(self):
        if self.running:
            return
        if not messagebox.askyesno(
            "Download SVD model",
            "This downloads several gigabytes from Hugging Face. Before continuing, "
            "accept the model license on its Hugging Face page and log in using "
            "the instructions in README.md.\n\nDownload now?",
            parent=self.root,
        ):
            return
        self.running = True
        self.generate_button.configure(state="disabled")
        self.setup_button.configure(state="disabled")
        self.status.set("Downloading model...")
        self.append_log("Downloading SVD model. Existing partial downloads can resume.")

        def worker():
            stdout = LogStream(sys.stdout, self.events)
            stderr = LogStream(sys.stderr, self.events)
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    download_model(COMPONENTS)
                stdout.finish()
                stderr.finish()
                self.events.put(("setup_done", str(COMPONENTS)))
            except Exception:
                stdout.finish()
                stderr.finish()
                self.events.put(("error", traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.append_log(value)
                elif kind == "status":
                    self.status.set(value)
                    self.append_log(value)
                elif kind == "done":
                    self.running = False
                    self.generate_button.configure(state="normal")
                    self.setup_button.configure(state="normal")
                    self.status.set(f"Saved: {value}")
                    self.append_log(f"Saved: {value}")
                    self.open_video(value)
                elif kind == "setup_done":
                    self.running = False
                    self.generate_button.configure(state="normal")
                    self.setup_button.configure(state="normal")
                    self.status.set("Model ready. Choose an image to begin.")
                    self.append_log(f"Model ready: {value}")
                elif kind == "error":
                    self.running = False
                    self.generate_button.configure(state="normal")
                    self.setup_button.configure(state="normal")
                    self.status.set("Operation failed. See the live log.")
                    self.append_log(value)
                    messagebox.showerror("Operation failed", value, parent=self.root)
        except queue.Empty:
            pass
        self.poll_id = self.root.after(100, self.poll)

    def open_video(self, path):
        self.stop_playback()
        try:
            self.reader = imageio.get_reader(str(path))
            metadata = self.reader.get_meta_data()
            fps = float(metadata["fps"])
            if fps <= 0:
                raise ValueError("Video has an invalid frame rate.")
            self.video_path = str(path)
            self.frame_delay = max(1, round(1000 / fps))
            self.playing = True
            self.play_button.configure(text="Pause", state="normal")
            self.append_log(f"Playing: {path}")
            self.show_next_frame()
        except Exception as exc:
            self.stop_playback()
            self.append_log(f"Could not open video: {exc}")
            messagebox.showerror("Video playback failed", str(exc), parent=self.root)

    def show_next_frame(self):
        self.after_id = None
        if not self.playing or self.reader is None:
            return
        try:
            try:
                frame = self.reader.get_next_data()
            except IndexError:
                self.reader.set_image_index(0)
                frame = self.reader.get_next_data()
            self.current_frame = Image.fromarray(frame)
            self.resize_frame()
            self.after_id = self.root.after(self.frame_delay, self.show_next_frame)
        except Exception as exc:
            self.stop_playback()
            self.append_log(f"Video playback failed: {exc}")
            messagebox.showerror("Video playback failed", str(exc), parent=self.root)

    def resize_frame(self, _event=None):
        if self.current_frame is None:
            return
        width, height = max(1, self.viewer.winfo_width()), max(1, self.viewer.winfo_height())
        frame = self.current_frame.copy()
        frame.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.frame_image = ImageTk.PhotoImage(frame)
        self.viewer.configure(image=self.frame_image, text="")

    def toggle_play(self):
        if self.reader is None:
            return
        self.playing = not self.playing
        self.play_button.configure(text="Pause" if self.playing else "Play")
        if self.playing:
            self.show_next_frame()
        elif self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def stop_playback(self):
        self.playing = False
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        self.play_button.configure(state="disabled", text="Pause")

    def close(self):
        if self.running and not messagebox.askyesno(
            "Operation in progress", "Stop the current operation and close?", parent=self.root
        ):
            return
        self.stop_playback()
        self.root.after_cancel(self.poll_id)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    VideoGeneratorV2(root)
    root.mainloop()
