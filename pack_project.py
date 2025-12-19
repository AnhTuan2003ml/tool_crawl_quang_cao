import os

# ================= CẤU HÌNH =================
# Tên file kết quả sẽ xuất ra
OUTPUT_FILE = "FULL_PROJECT_CONTEXT.txt"

# Các đuôi file code cần lấy (Sếp có thể thêm bớt)
INCLUDED_EXTENSIONS = {
    '.py', '.vue', '.ts', '.js', '.json', 
    '.css', '.html', '.env.example' ,'.env' 
    # Lưu ý: Không lấy .env thật để lộ key
}

# Các thư mục BẮT BUỘC BỎ QUA (để file không bị nặng)
IGNORE_DIRS = {
    'node_modules', 'venv', 'env', '__pycache__', '.git', 
    '.vscode', '.idea', 'dist', 'build', 
    'generated_images', 'final_videos', 'storage', 'temp'
}

# Các file cụ thể cần bỏ qua
IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'poetry.lock', 
    'pack_project.py', OUTPUT_FILE, '.DS_Store'
}
# ============================================

def is_ignored(path, is_dir=False):
    name = os.path.basename(path)
    if is_dir:
        return name in IGNORE_DIRS
    return name in IGNORE_FILES

def get_file_content(file_path):
    try:
        # Giới hạn file quá lớn (> 500KB) thì không đọc để tránh lag
        if os.path.getsize(file_path) > 500 * 1024: 
            return f"[FILE QUÁ LỚN - ĐÃ BỎ QUA NỘI DUNG]: {os.path.getsize(file_path)} bytes"
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"[LỖI KHÔNG ĐỌC ĐƯỢC FILE]: {e}"

def generate_tree(startpath):
    tree_str = "PROJECT STRUCTURE:\n"
    for root, dirs, files in os.walk(startpath):
        # Lọc folder ignore
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree_str += f"{indent}{os.path.basename(root)}/\n"
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            if not is_ignored(f):
                tree_str += f"{subindent}{f}\n"
    return tree_str

def main():
    root_dir = os.getcwd()
    print(f"🚀 Đang đóng gói dự án tại: {root_dir}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        # 1. Ghi thời gian và cấu trúc thư mục
        out.write(f"=== PROJECT CONTEXT EXPORT ===\n\n")
        out.write(generate_tree(root_dir))
        out.write("\n" + "="*50 + "\n\n")

        # 2. Duyệt file và ghi nội dung
        file_count = 0
        for root, dirs, files in os.walk(root_dir):
            # Lọc folder ignore ngay từ đầu
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if is_ignored(file): continue
                
                ext = os.path.splitext(file)[1].lower()
                if ext in INCLUDED_EXTENSIONS:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, root_dir)
                    
                    print(f" -> Đang gói: {rel_path}")
                    
                    content = get_file_content(file_path)
                    
                    # Format đẹp để AI dễ đọc
                    out.write(f"--- START FILE: {rel_path} ---\n")
                    out.write(content)
                    out.write(f"\n--- END FILE: {rel_path} ---\n\n")
                    file_count += 1

    print(f"\n✅ XONG! Đã đóng gói {file_count} file code.")
    print(f"📁 File kết quả: {os.path.join(root_dir, OUTPUT_FILE)}")
    print("👉 Hãy upload file này sang chat mới!")

if __name__ == "__main__":
    main()