# Doodle Beats Sounds

Kho âm thanh nhạc cụ (SoundFont `.sf2`) cho ứng dụng **Doodle Beats**. Mỗi nhạc cụ là một file `.sf2` độc lập, chỉ chứa đúng một preset, được tách ra từ bộ SoundFont **{{SOURCE}}** của S. Christian Collins. Ứng dụng tải file theo nhu cầu qua jsDelivr CDN.

*English: Per-instrument SoundFont files for the Doodle Beats app. Each `.sf2` holds exactly one preset split out of {{SOURCE}} by S. Christian Collins. The app downloads them on demand via jsDelivr.*

- Tổng số nhạc cụ / Instruments: **{{TOTAL_COUNT}}** ({{TOTAL_SIZE}})
- Nhạc cụ core (đóng gói sẵn trong app, không tải) / Core (bundled in the app): **{{CORE_COUNT}}** ({{CORE_SIZE}})

## Nguồn & giấy phép / Source & license

- Nguồn: GeneralUser GS v2.0.3 — tác giả S. Christian Collins
  - Trang chủ: https://www.schristiancollins.com/generaluser
  - GitHub: https://github.com/mrbumpy409/GeneralUser-GS
- Giấy phép gốc (không chỉnh sửa): [`LICENSE-GeneralUser-GS.txt`](LICENSE-GeneralUser-GS.txt). Trích:
  > You may use GeneralUser GS without restriction for your own music creation, private or commercial. [...] Please feel free to use it in your software projects, and to modify the SoundFont bank or its packaging to suit your needs.
- Các file ở đây là bản "đóng gói lại" (mỗi preset một file) — được giấy phép cho phép. Không bắt buộc ghi công, nhưng chúng tôi vẫn ghi công trong [`CREDITS.md`](CREDITS.md) và trong app.
- Tác giả yêu cầu không link trực tiếp tới file tải của ông; repo này tự host bản sao riêng (đúng như giấy phép gợi ý).

*English: The license allows unrestricted use (including commercial) and repackaging. Attribution is not required but is given in `CREDITS.md`. Please do not hot-link the author's own download files — this repo hosts its own copy.*

## Cấu trúc thư mục / Layout

```
manifest.json                  danh sách nhạc cụ (app đọc file này)
sf2/<group>/<key>.sf2          một file cho mỗi nhạc cụ, chia theo nhóm
LICENSE-GeneralUser-GS.txt     giấy phép gốc
CREDITS.md                     ghi công
tools/                         script tái tạo toàn bộ dữ liệu
```

## Quy tắc đặt tên / Naming

`<key>` = `b{bank:03d}_p{program:03d}` theo bank/program MIDI của preset gốc, ví dụ:

- `b000_p000` — Grand Piano (bank 0, program 0)
- `b008_p024` — Ukulele (bank biến thể 8, program 24)
- `b128_p000` — Standard 1 Kit (bank 128 = bộ trống)

`<group>` lấy theo họ nhạc cụ General MIDI (program / 8); bank 128 → `drums`.

## Ứng dụng tải file thế nào / How the app downloads

1. App đóng gói sẵn `manifest.json` và các nhạc cụ core.
2. Khi người dùng chọn một nhạc cụ chưa có, app tải:
   ```
   https://cdn.jsdelivr.net/gh/<user>/<repo>@main/sf2/<group>/<key>.sf2
   ```
   (đường dẫn tương đối nằm sẵn trong trường `path` của manifest; `baseUrl` = `https://cdn.jsdelivr.net/gh/<user>/<repo>@main`).
3. App kiểm tra `bytes` và `sha256`, lưu vào `<applicationSupportDirectory>/soundfonts/<key>.sf2`.

Nên dùng tag cố định (vd. `@v1`) thay cho `@main` khi phát hành để tránh cache jsDelivr trả bản cũ/mới lẫn lộn.

### manifest.json

```json
{
  "version": 1,
  "source": "{{SOURCE}}",
  "baseUrl": "",
  "groups": [{ "id": "piano", "name": "Piano", "order": 0 }],
  "instruments": [{
    "key": "b000_p004", "name": "Tine Electric Piano", "group": "piano",
    "bank": 0, "program": 4, "isDrum": false, "isCore": true,
    "bytes": 382582, "path": "sf2/piano/b000_p004.sf2", "sha256": "..."
  }]
}
```

## Thêm / cập nhật nhạc cụ / Adding or updating

1. Đặt file `GeneralUser-GS.sf2` và `LICENSE.txt` gốc vào `download/` (không commit).
2. Sửa danh sách bỏ qua / core / tên trong `tools/build.py` nếu cần.
3. Chạy `python3 -I tools/build.py` rồi `python3 -I tools/publish.py .` (xem [`tools/README.md`](tools/README.md)).
4. **Tăng `version` trong manifest** mỗi khi file thay đổi để app biết tải lại (sha256 khác → tải lại).
5. Commit, tạo tag mới, cập nhật manifest đóng gói trong app.

## Nhóm / Groups

{{TABLE}}
