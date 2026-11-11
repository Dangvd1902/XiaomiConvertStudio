# 📱 Xiaomi Convert ROM Studio (X-Convert)

> **Công cụ tự động hóa 100% quy trình tạo bản ROM Convert Quốc tế / Đài Loan Full OTA cho các dòng máy Xiaomi (Snapdragon 8 Gen 2 / 8 Gen 3 như Redmi K70 `vermeer`, K60, Xiaomi 14/13, v.v.).**

---

## 🌟 Tính Năng Nổi Bật (Key Features)

- ⚡ **Siêu tốc với NTFS HardLink**: Xử lý và liên kết toàn bộ gói ROM 15GB chỉ mất từ **1 đến 3 giây** mà không tốn thêm dung lượng ổ cứng.
- 🛠️ **Vá bảng phân vùng GPT tự động (Hardware Carrier Patch)**: 
  - Tự động thay thế phân vùng `opconfig` $\rightarrow$ `opcust`.
  - Tự động tính toán và cập nhật lại toàn bộ mã kiểm tra **CRC32** cho cả GPT Header và Partition Entry Array theo chuẩn Qualcomm UFS 4.0 & eMMC.
- 🔄 **Đồng bộ toàn diện Slot A/B (Full OTA)**: 
  - Quét và tự động đồng bộ 29 phân vùng Slot A sang Slot B (`abl`, `boot`, `modem`, `xbl`, `tz`, `dsp`, `vendor_boot`, `recovery`, v.v.) trong `rawprogram2.xml` và `rawprogram4.xml`.
  - Giúp thiết bị tự động cập nhật OTA bình thường trên điện thoại mà **không bao giờ lo bị brick khi đổi slot**.
- 🛡️ **Bảo vệ an toàn tuyệt đối phân vùng Persist & EFS**: 
  - Tự động bỏ trống trường filename của `persist` (`filename=""`), chống mất IMEI, mất vân tay hoặc lỗi cảm biến.
- 🔓 **Tự động nhúng Firehose No-Auth**: 
  - Tích hợp loader Qualcomm Firehose No-Auth để nạp trực tiếp qua cổng cứu hộ **EDL 9008** mà không cần tài khoản Xiaomi Authorized.
  - Tự động nhận diện loader nếu có thư mục ROM Factory / Engineering (ENG).
- 🧹 **Mặc định Flash Sạch (Clean Flash / Wipe Data)**: 
  - Tự động định cấu hình `userdata.img` nạp sạch sẽ, tránh hoàn toàn xung đột cơ sở dữ liệu và lỗi sập nguồn/treo logo.
- 📦 **Tự sinh gói nạp lẻ FIX_OTA**: 
  - Tạo sẵn `rawprogram0_CHI_NAP_FIX_OTA.xml` chứa 4 file cốt lõi (`opcust.img`, `misc.img`, `gpt_main0.bin`, `gpt_backup0.bin`) phục vụ việc fix nhanh.

---

## 🖥️ Giao Diện Đồ Họa (GUI)

Ứng dụng được viết trên nền tảng **PyQt6**, giao diện Dark Theme hiện đại, theo dõi tiến trình và nhật ký thời gian thực (Live Build Logs):

- **ROM Đích (Target ROM)**: Chọn thư mục ROM Fastboot chính hãng (file `.tgz` đã giải nén).
- **Firehose No-Auth**: Chọn file `.elf` hoặc `.melf` đã bypass authentication.
- **ROM ENG (Tùy chọn)**: Chọn thư mục ROM Factory nếu cần tự trích xuất loader.
- **Khu vực đích (Region)**: 
  - 🇹🇼 **Đài Loan (TW)**: Có sẵn ghi âm cuộc gọi tự động không thông báo.
  - 🌐 **Quốc Tế (Global)**
  - 🇪🇺 **Châu Âu (EEA)**
  - 🇮🇳 **Ấn Độ (India)**

---

## 🚀 Hướng Dẫn Sử Dụng

### Cách 1: Sử dụng File Thực Thi (.exe) chạy ngay không cần cài đặt
1. Tải bản phát hành mới nhất từ mục [Releases](https://github.com/Dangvd1902/XiaomiConvertStudio/releases).
2. Chạy file `XiaomiConvertStudio.exe`.
3. Chọn đường dẫn thư mục ROM và file Firehose.
4. Bấm **"🚀 BẮT ĐẦU TẠO ROM CONVERT (1-CLICK)"**.

### Cách 2: Chạy từ Mã Nguồn Python
```bash
# Cài đặt thư viện
pip install PyQt6

# Khởi chạy giao diện
python convert_gui.py
```

---

## 📋 Yêu Cầu Hệ Thống
- Hệ điều hành: Windows 10 / Windows 11 (64-bit).
- Phân vùng ổ đĩa: Khuyến nghị định dạng NTFS để tận dụng tính năng HardLink siêu tốc.

---

## ⚖️ Tuyên Bố Miễn Trừ Trách Nhiệm (Disclaimer)
Công cụ này được phát triển cho mục đích học tập, nghiên cứu và phục hồi thiết bị di động. Tác giả không chịu trách nhiệm đối với bất kỳ rủi ro phần cứng nào phát sinh do việc sử dụng sai quy trình.

---

## 👨‍💻 Tác Giả & Đóng Góp
- **Developer**: Dangvd1902
- **GitHub**: [@Dangvd1902](https://github.com/Dangvd1902)
