# obsidian-migrate 🚀

> **Selective Obsidian Vault Migration & Export CLI Tool**  
> Trích xuất và đồng bộ các ghi chú môn học (Class notes) từ một Obsidian Vault cá nhân nguyên khối (monolithic vault) sang một vault độc lập để chia sẻ với bạn bè và câu lạc bộ học tập mà không để lộ các ghi chú cá nhân riêng tư.

---

## 📌 Bối cảnh & Vấn đề giải quyết

Khi sử dụng Obsidian trong thời gian dài, chúng ta thường lưu trữ mọi thứ trong cùng một vault: từ bài giảng trên lớp (`Class`), đồ án nghiên cứu (`Lab`), tài chính & cuộc sống (`Life`), cho đến nhật ký cá nhân (`Thoughts`).

**Vấn đề phát sinh khi bạn muốn chia sẻ tài liệu học tập:**
- ❌ Nếu chia sẻ toàn bộ vault, các ghi chú cá nhân nhạy cảm (`Life`, `Thoughts`) sẽ bị lộ.
- ❌ Nếu copy thủ công từng bài giảng thì bất khả thi vì hàng trăm note liên kết chằng chịt với slide PDF, ảnh chụp màn hình, sơ đồ Canvas và bản vẽ Excalidraw. Thiếu một file ảnh là cả sơ đồ hoặc ghi chú sẽ bị lỗi hiển thị.
- ❌ Obsidian Dataview thường dùng query động (ví dụ `WHERE contains(subject, this.file.link)`) nên các bài học không được link cứng từ trang môn học, khiến các công cụ copy thông thường bỏ sót hoàn toàn.

**`obsidian-migrate`** ra đời để tự động hóa 100% quá trình trích xuất và đồng bộ này.

---

## ✨ Tính năng nổi bật

- 🎯 **Nhận diện môn học & bài giảng thông minh (Expanded Seed Discovery):**
  - Quét các môn học chính có khai báo `category: "[[Class]]"`.
  - Tự động nhận diện tất cả các bài học trỏ tới môn học đó (qua thuộc tính `subject: - "[[Class...]]"` hoặc liên kết wikilink trong nội dung).
- 🎨 **Giải quyết triệt để tài nguyên sơ đồ Canvas & Excalidraw:**
  - Đọc sâu vào cấu trúc JSON của file `.canvas` để lấy các node file và liên kết văn bản nhúng.
  - Phân tích file `.excalidraw.md` để tự động kéo theo mọi hình ảnh dán dở (`Pasted Image...`), đảm bảo sang vault mới bản vẽ hiển thị vẹn nguyên 100%.
- 🔗 **Bộ phân giải liên kết (Link Resolver) mạnh mẽ:**
  - Hỗ trợ cả wikilinks (`[[Note]]`, `[[folder/Note]]`, `[[Note|Alias]]`, `[[Note#Heading]]`) và Markdown links thông thường.
  - Cơ chế dò tìm theo tên file, stem không đuôi `.md`, xử lý đường dẫn tương đối và phát hiện liên kết mơ hồ (ambiguous links).
- 🛡️ **An toàn tuyệt đối với Vault gốc:**
  - Vault nguồn **hoàn toàn ở chế độ chỉ đọc (Read-only)**, không bao giờ bị chỉnh sửa.
  - Kiểm tra an toàn: ngăn chặn đệ quy (thư mục đích nằm trong thư mục nguồn hoặc ngược lại), cảnh báo khi thư mục đích không rỗng.
- ⚙️ **Đồng bộ toàn diện cấu hình Obsidian (`--include-obsidian`):**
  - Tự động sao chép toàn bộ thư mục `.obsidian/` (plugins, themes, hotkeys, snippets, workspace) để người nhận mở vault ra là dùng được ngay với giao diện chuẩn.

---

## 🏗️ Cấu trúc Module

```text
obsidian-migrate/
├── obsidian-migrate          # Executable entry script
├── pyproject.toml            # Package configuration
├── tests/
│   └── test_migrate.py       # Comprehensive test suite (62 test cases)
└── obsidian_migrate/
    ├── __init__.py
    ├── cli.py                # Command line interface & argument parsing
    ├── scanner.py            # Vault file scanner (excludes .obsidian, .git)
    ├── frontmatter.py        # YAML frontmatter parser
    ├── category.py           # Category normalization & seed detection
    ├── links.py              # Regex & JSON link extractors (wikilinks, markdown, canvas)
    ├── resolver.py           # Indexed link resolver with ambiguity detection
    ├── migrator.py           # Core migration planner & copy executor
    └── reporter.py           # Plan summary & statistics reporter
```

---

## 🚀 Cài đặt & Yêu cầu

- **Python:** `>= 3.10`
- **Thư viện phụ thuộc:** `pyyaml`

Cài đặt thư viện yêu cầu:
```bash
pip install pyyaml
```

---

## 📖 Hướng dẫn sử dụng

### Cú pháp lệnh:

```bash
python3 obsidian-migrate <source_vault> <destination_vault> [options]
```

### Các tùy chọn (CLI Options):

| Tùy chọn | Mô tả |
| :--- | :--- |
| `source` | Đường dẫn tới Vault nguồn (chỉ đọc) |
| `destination` | Đường dẫn tới Vault đích xuất ra |
| `--dry-run` | Chạy thử mô phỏng, liệt kê danh sách file và liên kết mà không copy |
| `-v`, `--verbose` | In chi tiết tiến trình quét và danh sách file sao chép |
| `--force` | Cho phép ghi đè/cập nhật vào thư mục đích nếu đã có dữ liệu |
| `--include-obsidian` | Sao chép toàn bộ thư mục cấu hình `.obsidian/` (giao diện, phím tắt, plugin) |

---

## 💡 Ví dụ thực tế

### 1. Chạy thử nghiệm xem trước (Dry-run):
```bash
python3 obsidian-migrate /path/to/my-vault /path/to/share-vault --dry-run
```

### 2. Thực hiện trích xuất và đồng bộ đầy đủ:
```bash
python3 obsidian-migrate \
    /mnt/lamviec/keepskyclear.Obsidian \
    /mnt/lamviec/keepskyclear.Obsidian.share \
    --force --include-obsidian --verbose
```

### Kết quả hiển thị mẫu:
```text
Migration complete.

Class seeds:             133
Markdown dependencies:   232
Asset dependencies:      506
Total files copied:      871

Unresolved links:        149
Ambiguous links:         24
```

---

## 🧪 Kiểm thử (Unit Testing)

Bộ test suite toàn diện với **62 test cases** kiểm tra toàn bộ các khía cạnh:
- Nhận diện seed và chuẩn hóa YAML frontmatter.
- Trích xuất wikilink, markdown link, Canvas JSON nodes, Excalidraw embeds.
- Cơ chế giải quyết liên kết và xử lý mơ hồ.
- Giới hạn độ sâu 1-hop và an toàn hệ thống tập tin.

Chạy test suite:
```bash
python3 -m unittest tests.test_migrate -v
```

Kết quả:
```text
Ran 62 tests in 0.013s
OK
```

---

## 📄 Bản quyền & Tác giả

Phát triển bởi **DatHoang** phục vụ cho hệ thống ghi chép học tập cá nhân và chia sẻ tài liệu câu lạc bộ.
Mã nguồn mở theo giấy phép MIT.
