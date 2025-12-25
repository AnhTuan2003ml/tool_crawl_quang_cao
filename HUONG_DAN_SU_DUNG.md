# HƯỚNG DẪN SỬ DỤNG HỆ THỐNG QUÉT FACEBOOK

## 🎯 Tổng quan
Hệ thống này giúp tự động hóa việc quét và quản lý dữ liệu quảng cáo trên Facebook, hỗ trợ scale quảng cáo hiệu quả.

## 📋 Các Trang/Chức Năng Chính

### 1. 📋 **Trang Kết Quả** (Scan Results)
- **Chức năng**: Hiển thị dữ liệu đã quét được từ Facebook
- **Các bộ lọc**:
  - **🔍 Lọc theo màu**: Phân loại dữ liệu theo độ ưu tiên
    - 🟢 **Xanh (type1)**: Dữ liệu ưu tiên cao, dữ liệu đối thủ
    - 🟡 **Vàng (type2)**: Dữ liệu ưu tiên trung bình
    - 🔴 **Đỏ (type3)**: Dữ liệu từ tìm kiếm khách hàng
  - **📊 Lọc theo tương tác**: Có/Không có React, Comment
  - **⏰ Lọc theo thời gian**: Chọn khoảng thời gian cụ thể
### 2. 📝 **Trang Quản Lý Post** (Post Manager)
- **Chức năng**: Quản lý danh sách các bài post được theo dõi
- **Nguồn dữ liệu**: Đọc từ file JSON trong thư mục `post_ids`
- **Thông tin hiển thị**: ID Post, Nội dung, Loại (Type)

### 3. ⚙️ **Trang Cài Đặt** (Settings)
- **Chức năng**: Cấu hình hệ thống và quản lý profile
- **Các tính năng chính**:
  - **API Key**: Cài đặt key để kết nối với backend
  - **Quản lý Profile**: Thêm/xóa/sửa profile Facebook
  - **Chức năng tự động**:
    - Lấy thông tin profile
    - Quét bài viết
    - Quét theo nhóm
    - Tự động tham gia nhóm
    - Nuôi tài khoản (Feed)
### Xuất dữ liệu:
- **📊 Xuất file Excel**: Xuất toàn bộ dữ liệu thành file Excel
### 2. **Quét bài viết**
- Tương tự như Feed nhưng tập trung vào việc thu thập dữ liệu
- Hỗ trợ lọc theo keyword và rule tự động
### 3. **Quét theo nhóm**
- Quét dữ liệu từ các nhóm Facebook cụ thể
- Cài đặt số lượng bài viết và khoảng thời gian
- Nhập URL nhóm (mỗi dòng một URL)

## 🔄 Quy trình sử dụng

1. **Khởi động**: Mở trang web và chờ backend sẵn sàng
2. **Cài đặt**: Nhập API Key và thêm profile
3. **Cấu hình**: Setting thời gian và điều kiện quét
4. **Chạy**: Bắt đầu quét và theo dõi kết quả
5. **Xuất dữ liệu**: Export Excel khi cần phân tích
