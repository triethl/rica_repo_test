# Comic Downloader

Công cụ Python tải ảnh truyện theo từng chương về máy.
**Chỉ dùng cho nội dung bạn có quyền sao chép**: truyện của chính bạn, phạm vi công cộng, Creative Commons, hoặc được tác giả cho phép.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cách dùng

```bash
python downloader.py "https://example.com/comic/ten-truyen" \
  --chapter-selector "ul.chapter-list a" \
  --image-selector "div.reader img" \
  --reverse \
  --cbz \
  --confirm-rights
```

| Tham số | Ý nghĩa |
|---|---|
| `url` | Trang truyện chứa danh sách chương |
| `--chapters-file ds.txt` | Thay cho `url`: file mỗi dòng một URL chương |
| `--chapter-selector` | CSS selector của link chương |
| `--image-selector` | CSS selector của ảnh trong trang chương |
| `--reverse` | Đảo thứ tự nếu trang liệt kê chương mới nhất trước |
| `--start N` / `--end M` | Chỉ tải chương N đến M |
| `--out thu_muc` | Thư mục lưu (mặc định `downloads`) |
| `--workers 4` | Số ảnh tải song song |
| `--delay 1.0` | Giây nghỉ trước mỗi lần tải trang HTML |
| `--cbz` / `--pdf` | Đóng gói từng chương |
| `--confirm-rights` | **Bắt buộc**, xác nhận bạn có quyền tải |

Kết quả:

```
downloads/
└── Ten truyen/
    ├── 001 - Chapter 1/
    │   ├── 001.jpg
    │   └── 002.jpg
    ├── 001 - Chapter 1.cbz
    └── ...
```

## Giao diện đồ họa (GUI)

```powershell
py gui.py
```

(`gui.py` và `downloader.py` phải nằm cùng thư mục. Giao diện dùng `tkinter`, có sẵn khi cài Python từ python.org.)

Các bước:

1. Nhập URL trang truyện, selector link chương và selector ảnh.
2. Tick ô xác nhận bạn có quyền sao chép nội dung.
3. Bấm **Tải danh sách chương**. Danh sách hiện trong khung giữa; chọn chương muốn tải (Ctrl/Shift để chọn nhiều), không chọn gì thì tải tất cả.
4. Bấm **Bắt đầu tải**. Thanh tiến trình và nhật ký cho biết tiến độ; bấm **Dừng** để dừng giữa chừng, chạy lại sẽ tải tiếp phần còn thiếu.
5. Bấm **Mở thư mục** để xem kết quả.

### Đóng gói thành file .exe (Windows)

```powershell
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed gui.py
```

File `dist\gui.exe` chạy được trên máy khác mà không cần cài Python.

## Tìm CSS selector

1. Mở trang truyện trong trình duyệt, nhấn **F12**.
2. Dùng công cụ chọn phần tử (Ctrl+Shift+C), bấm vào một link chương, xem thẻ `<a>` nằm trong thẻ cha nào (ví dụ `ul.chapter-list`) rồi viết `ul.chapter-list a`.
3. Làm tương tự trong trang chương để tìm selector của ảnh, ví dụ `div.reader img`.
4. Công cụ tự đọc các thuộc tính `data-src`, `data-original`, `data-lazy-src`, `src` (ảnh lazy-load).

## Tính năng

- Tải song song, tự thử lại khi lỗi mạng hoặc bị giới hạn (429/5xx).
- Chạy lại cùng lệnh sẽ bỏ qua ảnh đã tải (resume).
- Tôn trọng `robots.txt` và có độ trễ giữa các lần tải trang.
- Gửi `Referer` đúng trang chương (một số máy chủ ảnh yêu cầu).

## Giới hạn

- Chỉ đọc HTML tĩnh. Nếu danh sách chương hoặc ảnh được nạp bằng JavaScript/API, hãy lấy danh sách URL chương từ tab Network của trình duyệt, lưu vào file `.txt` rồi dùng `--chapters-file`.
- Nếu trang có nút "Xem thêm" để hiện thêm chương, cần xử lý riêng (gọi API mà nút đó dùng).
