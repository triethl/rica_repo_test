#!/usr/bin/env python3
"""
Tải ảnh truyện theo từng chương về máy.

CHỈ dùng cho nội dung bạn có quyền sao chép (truyện của chính bạn,
phạm vi công cộng, Creative Commons, hoặc được tác giả cho phép).
"""
import argparse
import mimetypes
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from tqdm import tqdm
except ImportError:  # tqdm là tùy chọn: không có thì không hiện thanh tiến trình
    class tqdm:
        def __init__(self, iterable=None, **kwargs):
            self.iterable = iterable

        def __iter__(self):
            return iter(self.iterable)

        @staticmethod
        def write(msg):
            print(msg)

IMG_ATTRS = ("data-src", "data-original", "data-lazy-src", "src")
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


# ---------- tiện ích ----------
def sanitize(name: str, maxlen: int = 80) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", name).strip(" .")
    return re.sub(r"\s+", " ", name)[:maxlen] or "untitled"


def make_session(user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = user_agent
    retry = Retry(
        total=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    adapter = HTTPAdapter(max_retries=retry, pool_maxsize=32)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def allowed_by_robots(session: requests.Session, url: str, ua: str) -> bool:
    p = urlparse(url)
    rp = RobotFileParser()
    try:
        r = session.get(f"{p.scheme}://{p.netloc}/robots.txt", timeout=15)
        if r.status_code >= 400:
            return True
        rp.parse(r.text.splitlines())
    except requests.RequestException:
        return True
    return rp.can_fetch(ua, url)


def get_soup(session: requests.Session, url: str, delay: float) -> BeautifulSoup:
    time.sleep(delay)
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ---------- phân tích trang ----------
def extract_chapters(soup, base_url, selector):
    """Trả về list[(tiêu đề, url)] theo thứ tự xuất hiện, bỏ trùng."""
    seen, out = set(), []
    for a in soup.select(selector):
        href = a.get("href")
        if not href or href.startswith(("#", "javascript:")):
            continue
        url = urljoin(base_url, href)
        if url in seen:
            continue
        seen.add(url)
        out.append((a.get_text(" ", strip=True) or f"chapter {len(out) + 1}", url))
    return out


def extract_images(soup, base_url, selector):
    seen, out = set(), []
    for img in soup.select(selector):
        src = next((img.get(a) for a in IMG_ATTRS if img.get(a)), None)
        if not src:
            continue
        src = src.strip()
        if src.startswith("data:"):
            continue
        url = urljoin(base_url, src)
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


# ---------- tải ảnh ----------
def download_image(session, url, dest_stem: Path, referer: str) -> bool:
    # Resume: bỏ qua nếu đã có file (bất kể đuôi)
    for p in dest_stem.parent.glob(dest_stem.name + ".*"):
        if p.suffix != ".part":
            return True
    try:
        with session.get(url, headers={"Referer": referer}, stream=True, timeout=30) as r:
            r.raise_for_status()
            ctype = r.headers.get("Content-Type", "").split(";")[0].strip()
            if ctype and not ctype.startswith("image/"):
                return False
            ext = Path(urlparse(url).path).suffix.lower()
            if ext not in IMG_EXTS:
                ext = mimetypes.guess_extension(ctype) or ".jpg"
            dest = dest_stem.with_name(dest_stem.name + ext)
            part = dest.with_name(dest.name + ".part")
            with open(part, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
            part.replace(dest)
        return True
    except requests.RequestException:
        return False


def download_chapter(session, title, ch_url, ch_dir: Path, args):
    ch_dir.mkdir(parents=True, exist_ok=True)
    soup = get_soup(session, ch_url, args.delay)
    images = extract_images(soup, ch_url, args.image_selector)
    if not images:
        tqdm.write(f"  ! Không tìm thấy ảnh ở {ch_url} (kiểm tra --image-selector)")
        return 0, 0
    width = max(3, len(str(len(images))))
    jobs = [(u, ch_dir / str(i).zfill(width)) for i, u in enumerate(images, 1)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(
            tqdm(
                pool.map(lambda j: download_image(session, j[0], j[1], ch_url), jobs),
                total=len(jobs),
                desc=f"  {title[:40]}",
                unit="ảnh",
                leave=False,
            )
        )
    return sum(results), len(results)


# ---------- đóng gói ----------
def sorted_images(ch_dir: Path):
    return sorted(p for p in ch_dir.iterdir() if p.suffix.lower() in IMG_EXTS)


def make_cbz(ch_dir: Path):
    with zipfile.ZipFile(ch_dir.with_suffix(".cbz"), "w", zipfile.ZIP_STORED) as z:
        for p in sorted_images(ch_dir):
            z.write(p, p.name)


def make_pdf(ch_dir: Path):
    try:
        from PIL import Image
    except ImportError:
        tqdm.write("  ! Cần cài Pillow để tạo PDF: pip install Pillow")
        return
    files = sorted_images(ch_dir)
    if not files:
        return
    pages = [Image.open(p).convert("RGB") for p in files]
    pages[0].save(ch_dir.with_suffix(".pdf"), save_all=True, append_images=pages[1:])


# ---------- main ----------
def parse_args():
    ap = argparse.ArgumentParser(description="Tải ảnh truyện theo chương (nội dung bạn có quyền sao chép).")
    ap.add_argument("url", nargs="?", help="URL trang truyện chứa danh sách chương")
    ap.add_argument("--chapters-file", help="File .txt, mỗi dòng một URL chương (thay cho url)")
    ap.add_argument("--chapter-selector", default="a",
                    help="CSS selector của link chương, vd: 'ul.chapters a'")
    ap.add_argument("--image-selector", default="img",
                    help="CSS selector của ảnh trong trang chương, vd: 'div.reader img'")
    ap.add_argument("--reverse", action="store_true",
                    help="Đảo thứ tự danh sách chương (khi trang liệt kê mới nhất trước)")
    ap.add_argument("--start", type=int, default=1, help="Chương bắt đầu (1-based, sau khi sắp xếp)")
    ap.add_argument("--end", type=int, default=0, help="Chương kết thúc (0 = hết)")
    ap.add_argument("--name", help="Tên thư mục truyện (mặc định lấy từ <title>)")
    ap.add_argument("--out", default="downloads", help="Thư mục lưu")
    ap.add_argument("--workers", type=int, default=4, help="Số luồng tải ảnh song song")
    ap.add_argument("--delay", type=float, default=1.0, help="Giây nghỉ trước mỗi lần tải trang HTML")
    ap.add_argument("--cbz", action="store_true", help="Đóng gói mỗi chương thành .cbz")
    ap.add_argument("--pdf", action="store_true", help="Đóng gói mỗi chương thành .pdf")
    ap.add_argument("--ignore-robots", action="store_true", help="Bỏ qua robots.txt (không khuyến khích)")
    ap.add_argument("--user-agent", default="Mozilla/5.0 (compatible; PersonalComicDownloader/1.0)")
    ap.add_argument("--confirm-rights", action="store_true",
                    help="Xác nhận bạn có quyền sao chép nội dung này (bắt buộc)")
    return ap.parse_args()


def main():
    args = parse_args()

    if not args.confirm_rights:
        sys.exit("Thêm --confirm-rights để xác nhận bạn có quyền tải nội dung này "
                 "(của bạn, phạm vi công cộng, CC, hoặc được tác giả cho phép).")
    if not args.url and not args.chapters_file:
        sys.exit("Cần truyền URL truyện hoặc --chapters-file.")

    session = make_session(args.user_agent)

    # 1) Lấy danh sách chương
    if args.chapters_file:
        lines = [l.strip() for l in Path(args.chapters_file).read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        chapters = [(f"chapter {i}", u) for i, u in enumerate(lines, 1)]
        series_name = args.name or Path(args.chapters_file).stem
        probe_url = lines[0] if lines else ""
    else:
        probe_url = args.url
        if not args.ignore_robots and not allowed_by_robots(session, probe_url, args.user_agent):
            sys.exit("robots.txt của trang không cho phép tải URL này. Dừng lại.")
        soup = get_soup(session, args.url, 0)
        chapters = extract_chapters(soup, args.url, args.chapter_selector)
        title_tag = soup.find("h1") or soup.title
        series_name = args.name or (title_tag.get_text(strip=True) if title_tag else "series")

    if not chapters:
        sys.exit("Không tìm thấy chương nào. Kiểm tra lại --chapter-selector.")
    if args.reverse:
        chapters.reverse()

    end = args.end or len(chapters)
    selected = list(enumerate(chapters, 1))[args.start - 1:end]
    print(f"Truyện: {series_name} | {len(selected)}/{len(chapters)} chương được chọn")

    if (not args.ignore_robots and args.chapters_file and probe_url
            and not allowed_by_robots(session, probe_url, args.user_agent)):
        sys.exit("robots.txt của trang không cho phép tải URL này. Dừng lại.")

    # 2) Tải từng chương
    series_dir = Path(args.out) / sanitize(series_name)
    failed = []
    for idx, (title, url) in tqdm(selected, desc="Chương", unit="chương"):
        ch_dir = series_dir / f"{idx:03d} - {sanitize(title)}"
        try:
            ok, total = download_chapter(session, title, url, ch_dir, args)
        except requests.RequestException as e:
            tqdm.write(f"  ! Lỗi tải chương {idx}: {e}")
            failed.append(url)
            continue
        if total and ok < total:
            tqdm.write(f"  ! Chương {idx}: chỉ tải {ok}/{total} ảnh (chạy lại để tải phần thiếu)")
            failed.append(url)
        if ok:
            if args.cbz:
                make_cbz(ch_dir)
            if args.pdf:
                make_pdf(ch_dir)

    print(f"Xong. Lưu tại: {series_dir.resolve()}")
    if failed:
        print(f"{len(failed)} chương chưa đủ ảnh. Chạy lại cùng lệnh, ảnh đã tải sẽ được bỏ qua.")


if __name__ == "__main__":
    main()
