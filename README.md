# Cuối Kỳ Visualization - Hướng dẫn cài đặt và sử dụng

## 1. Mục đích
Dự án này thu thập dữ liệu khí tượng thủy văn (KTTV) Việt Nam 2026 từ API Open-Meteo, lưu dữ liệu theo tỉnh/thành và gộp thành một file tổng.

## 2. Cấu trúc chính
- `script/01_crawl.py` : script thu thập dữ liệu từ Open-Meteo và xuất file CSV.
- `script/02_preprocess.py` : hiện tại chưa có nội dung cụ thể.
- `data/raw/openmeteo_2026/` : thư mục đầu ra cho từng file tỉnh/thành.
- `data/raw/` : chứa file gộp toàn quốc.
- `venv_kttv/` : môi trường ảo Python có sẵn.

## 2.1. Cách crawl hiện tại
- Mỗi tỉnh/thành không còn crawl một điểm duy nhất.
- `script/01_crawl.py` lấy 5 điểm quanh centroid cho tỉnh thông thường.
- Các tỉnh diện tích lớn sẽ lấy 9 điểm để tăng độ đại diện không gian.
- Dữ liệu các điểm sau đó được gộp theo ngày bằng trung bình cho các biến số và lấy mode cho các biến phân loại chính.

## 3. Yêu cầu hệ thống
- Windows
- Python 3.14 (môi trường `venv_kttv` hiện tại dùng Python 3.14)
- Kết nối Internet để gọi API Open-Meteo.

## 4. Cài đặt
1. Mở terminal và vào thư mục dự án:
   ```powershell
   cd d:\CODE\CuoiKy_Visualization
   ```
2. Kích hoạt môi trường ảo:
   - Nếu dùng Command Prompt:
     ```cmd
     venv_kttv\Scripts\activate
     ```
   - Nếu dùng PowerShell:
     ```powershell
     .\venv_kttv\Scripts\Activate.ps1
     ```
3. Cập nhật pip và cài đặt thư viện:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 5. Chạy thu thập dữ liệu
1. Chạy script chính:
   ```powershell
   python script\01_crawl.py
   ```
2. Kết quả sẽ lưu:
   - File dữ liệu từng tỉnh/thành vào `data/raw/openmeteo_2026/`
   - File gộp toàn quốc vào `data/raw/vietnam_kttv_34tinh_<START_DATE>_<END_DATE>.csv`

### 5.1. Lưu ý khi chạy
- Script tự động tạo thư mục `data/raw/openmeteo_2026` nếu chưa tồn tại.
- Nếu một file tỉnh/thành đã tồn tại, script sẽ bỏ qua và dùng file đó để tiết kiệm thời gian.
- Nếu API bị giới hạn (`429`), script sẽ chờ và tiếp tục.

## 6. Kiểm tra dữ liệu đầu ra
- Mở file CSV bằng Excel, LibreOffice Calc hoặc pandas.
- File gộp toàn quốc chứa các cột chính như `province`, `region`, `date`, `temperature_2m_mean`, `precipitation_sum`, `sunrise`, `sunset`, `season`, `month`, `week`, v.v.

## 7. Tùy chỉnh cơ bản
- Nếu muốn thay đổi khoảng thời gian dữ liệu, chỉnh `START_DATE` và `END_DATE` trong `script/01_crawl.py`.
- Nếu muốn thay đổi danh sách tỉnh/thành hoặc tọa độ, chỉnh `PROVINCES` trong cùng file.

## 8. Tiếp theo
- `script/02_preprocess.py` hiện đang trống. Bạn có thể thêm xử lý tiền xử lý dữ liệu hoặc trực quan hóa sau khi `01_crawl.py` đã tạo dữ liệu.
