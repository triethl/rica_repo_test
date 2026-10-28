#!/usr/bin/env python3
"""
Giao diện đồ họa cho Comic Downloader (tkinter).

CHỈ dùng cho nội dung bạn có quyền sao chép (truyện của chính bạn,
phạm vi công cộng, Creative Commons, hoặc được tác giả cho phép).
Cần để file này cùng thư mục với downloader.py.
"""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import requests

import downloader as dl

UA = "Mozilla/5.0 (compatible; PersonalComicDownloader/1.0)"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Comic Downloader")
        self.geometry("860x720")
        self.minsize(760, 640)

        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.chapters = []  # [(idx, title, url)]

        self.url = tk.StringVar()
        self.ch_sel = tk.StringVar(value="a")
        self.img_sel = tk.StringVar(value="img")
        self.name = tk.StringVar()
        self.out = tk.StringVar(value=str(Path.home() / "Downloads" / "comics"))
        self.workers = tk.IntVar(value=4)
        self.delay = tk.DoubleVar(value=1.0)
        self.reverse = tk.BooleanVar(value=False)
        self.cbz = tk.BooleanVar(value=False)
        self.pdf = tk.BooleanVar(value=False)
        self.rights = tk.BooleanVar(value=False)

        self._build()
        self.after(100, self._poll)

    # ---------- giao diện ----------
    def _build(self):
        pad = {"padx": 8, "pady": 4}
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=10, pady=10)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(8, weight=1)  # danh sách chương
        root.rowconfigure(11, weight=1)  # nhật ký

        ttk.Label(root, text="URL trang truyện:").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(root, textvariable=self.url).grid(row=0, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(root, text="Selector link chương:").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(root, textvariable=self.ch_sel).grid(row=1, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(root, text="Selector ảnh:").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(root, textvariable=self.img_sel).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(root, text="Tên thư mục truyện:").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(root, textvariable=self.name).grid(row=3, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(root, text="Thư mục lưu:").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(root, textvariable=self.out).grid(row=4, column=1, sticky="ew", **pad)
        ttk.Button(root, text="Chọn...", command=self._browse).grid(row=4, column=2, **pad)

        opts = ttk.Frame(root)
        opts.grid(row=5, column=0, columnspan=3, sticky="w", **pad)
        ttk.Label(opts, text="Số luồng:").pack(side="left")
        ttk.Spinbox(opts, from_=1, to=16, width=4, textvariable=self.workers).pack(side="left", padx=(4, 14))
        ttk.Label(opts, text="Nghỉ (giây):").pack(side="left")
        ttk.Spinbox(opts, from_=0, to=10, increment=0.5, width=5, textvariable=self.delay).pack(side="left", padx=(4, 14))
        ttk.Checkbutton(opts, text="Đảo thứ tự chương", variable=self.reverse).pack(side="left", padx=6)
        ttk.Checkbutton(opts, text="Tạo CBZ", variable=self.cbz).pack(side="left", padx=6)
        ttk.Checkbutton(opts, text="Tạo PDF", variable=self.pdf).pack(side="left", padx=6)

        ttk.Checkbutton(
            root,
            text="Tôi xác nhận có quyền sao chép nội dung này "
                 "(của tôi, phạm vi công cộng, CC, hoặc được tác giả cho phép)",
            variable=self.rights,
        ).grid(row=6, column=0, columnspan=3, sticky="w", **pad)

        bar = ttk.Frame(root)
        bar.grid(row=7, column=0, columnspan=3, sticky="ew", **pad)
        self.btn_load = ttk.Button(bar, text="1. Tải danh sách chương", command=self.load_chapters)
        self.btn_load.pack(side="left")
        ttk.Button(bar, text="Chọn tất cả", command=lambda: self.listbox.select_set(0, "end")).pack(side="left", padx=6)
        ttk.Button(bar, text="Bỏ chọn", command=lambda: self.listbox.select_clear(0, "end")).pack(side="left")

        lf = ttk.Frame(root)
        lf.grid(row=8, column=0, columnspan=3, sticky="nsew", **pad)
        lf.rowconfigure(0, weight=1)
        lf.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(lf, selectmode="extended", height=8, exportselection=False)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        run = ttk.Frame(root)
        run.grid(row=9, column=0, columnspan=3, sticky="ew", **pad)
        self.btn_start = ttk.Button(run, text="2. Bắt đầu tải (chương đã chọn, hoặc tất cả)", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(run, text="Dừng", command=self.stop, state="disabled")
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(run, text="Mở thư mục", command=self._open_folder).pack(side="left")

        self.progress = ttk.Progressbar(root, maximum=100)
        self.progress.grid(row=10, column=0, columnspan=3, sticky="ew", **pad)

        gf = ttk.Frame(root)
        gf.grid(row=11, column=0, columnspan=3, sticky="nsew", **pad)
        gf.rowconfigure(0, weight=1)
        gf.columnconfigure(0, weight=1)
        self.log_box = tk.Text(gf, height=8, state="disabled", wrap="word")
        lsb = ttk.Scrollbar(gf, orient="vertical", command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=lsb.set)
        self.log_box.grid(row=0, column=0, sticky="nsew")
        lsb.grid(row=0, column=1, sticky="ns")

    # ---------- tiện ích UI ----------
    def log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.out.get() or str(Path.home()))
        if d:
            self.out.set(d)

    def _open_folder(self):
        path = Path(self.out.get())
        if not path.exists():
            messagebox.showinfo("Thông báo", "Thư mục chưa tồn tại.")
            return
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])

    def _set_busy(self, busy):
        self.btn_load.configure(state="disabled" if busy else "normal")
        self.btn_start.configure(state="disabled" if busy else "normal")

    def _validate(self):
        if not self.url.get().strip():
            messagebox.showwarning("Thiếu thông tin", "Hãy nhập URL trang truyện.")
            return False
        if not self.rights.get():
            messagebox.showwarning(
                "Cần xác nhận",
                "Hãy tick ô xác nhận bạn có quyền sao chép nội dung này.",
            )
            return False
        return True

    # ---------- tải danh sách chương ----------
    def load_chapters(self):
        if not self._validate():
            return
        self._set_busy(True)
        self.log("Đang tải danh sách chương...")
        threading.Thread(
            target=self._load_worker,
            args=(self.url.get().strip(), self.ch_sel.get().strip() or "a", self.reverse.get()),
            daemon=True,
        ).start()

    def _load_worker(self, url, selector, reverse):
        try:
            s = dl.make_session(UA)
            if not dl.allowed_by_robots(s, url, UA):
                raise RuntimeError("robots.txt của trang không cho phép tải URL này.")
            soup = dl.get_soup(s, url, 0)
            chapters = dl.extract_chapters(soup, url, selector)
            if reverse:
                chapters.reverse()
            tag = soup.find("h1") or soup.title
            name = tag.get_text(strip=True) if tag else "series"
            self.q.put(("chapters", chapters, name))
        except Exception as e:  # noqa
            self.q.put(("error", str(e)))

    # ---------- tải ảnh ----------
    def start(self):
        if not self._validate():
            return
        if not self.chapters:
            messagebox.showinfo("Chưa có chương", "Hãy bấm 'Tải danh sách chương' trước.")
            return
        sel = self.listbox.curselection()
        indices = list(sel) if sel else list(range(len(self.chapters)))
        jobs = [self.chapters[i] for i in indices]
        series = dl.sanitize(self.name.get().strip() or "series")
        series_dir = Path(self.out.get()) / series
        opts = {
            "img_sel": self.img_sel.get().strip() or "img",
            "workers": max(1, int(self.workers.get())),
            "delay": max(0.0, float(self.delay.get())),
            "cbz": self.cbz.get(),
            "pdf": self.pdf.get(),
        }
        self.stop_event.clear()
        self._set_busy(True)
        self.btn_stop.configure(state="normal")
        self.progress["value"] = 0
        self.log(f"Bắt đầu tải {len(jobs)} chương vào: {series_dir}")
        threading.Thread(target=self._download_worker, args=(jobs, series_dir, opts), daemon=True).start()

    def stop(self):
        self.stop_event.set()
        self.log("Đang dừng... (chờ các ảnh đang tải xong)")

    def _download_worker(self, jobs, series_dir, opts):
        s = dl.make_session(UA)
        total = len(jobs)
        try:
            for n, (idx, title, url) in enumerate(jobs):
                if self.stop_event.is_set():
                    break
                ch_dir = series_dir / f"{idx:03d} - {dl.sanitize(title)}"
                ch_dir.mkdir(parents=True, exist_ok=True)
                self.q.put(("log", f"[{n + 1}/{total}] {title}"))
                try:
                    soup = dl.get_soup(s, url, opts["delay"])
                except requests.RequestException as e:
                    self.q.put(("log", f"  ! Lỗi tải trang chương: {e}"))
                    continue
                images = dl.extract_images(soup, url, opts["img_sel"])
                if not images:
                    self.q.put(("log", "  ! Không tìm thấy ảnh (kiểm tra selector ảnh)"))
                    continue

                width = max(3, len(str(len(images))))

                def job(arg, _dir=ch_dir, _w=width, _url=url):
                    if self.stop_event.is_set():
                        return False
                    i, u = arg
                    return dl.download_image(s, u, _dir / str(i).zfill(_w), _url)

                ok = 0
                with ThreadPoolExecutor(max_workers=opts["workers"]) as pool:
                    for k, res in enumerate(pool.map(job, enumerate(images, 1)), 1):
                        ok += bool(res)
                        self.q.put(("progress", (n + k / len(images)) / total * 100))

                if ok < len(images) and not self.stop_event.is_set():
                    self.q.put(("log", f"  ! Chỉ tải {ok}/{len(images)} ảnh (chạy lại để tải phần thiếu)"))
                if ok and not self.stop_event.is_set():
                    try:
                        if opts["cbz"]:
                            dl.make_cbz(ch_dir)
                        if opts["pdf"]:
                            dl.make_pdf(ch_dir)
                    except Exception as e:  # noqa
                        self.q.put(("log", f"  ! Lỗi đóng gói: {e}"))
            self.q.put(("done", self.stop_event.is_set()))
        except Exception as e:  # noqa
            self.q.put(("error", str(e)))

    # ---------- nhận thông điệp từ luồng nền ----------
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "log":
                    self.log(msg[1])
                elif kind == "progress":
                    self.progress["value"] = msg[1]
                elif kind == "chapters":
                    chapters, name = msg[1], msg[2]
                    self.chapters = [(i, t, u) for i, (t, u) in enumerate(chapters, 1)]
                    self.listbox.delete(0, "end")
                    for i, t, _ in self.chapters:
                        self.listbox.insert("end", f"{i:03d} - {t}")
                    if not self.name.get().strip():
                        self.name.set(name)
                    self._set_busy(False)
                    if self.chapters:
                        self.log(f"Tìm thấy {len(self.chapters)} chương.")
                    else:
                        self.log("Không tìm thấy chương nào. Kiểm tra lại selector link chương.")
                elif kind == "done":
                    self._set_busy(False)
                    self.btn_stop.configure(state="disabled")
                    if not msg[1]:
                        self.progress["value"] = 100
                    self.log("Đã dừng." if msg[1] else "Hoàn tất.")
                elif kind == "error":
                    self._set_busy(False)
                    self.btn_stop.configure(state="disabled")
                    self.log(f"Lỗi: {msg[1]}")
                    messagebox.showerror("Lỗi", msg[1])
        except queue.Empty:
            pass
        self.after(100, self._poll)


if __name__ == "__main__":
    App().mainloop()
