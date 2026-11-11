import os
import sys
import shutil
import struct
import zlib
import re
import xml.etree.ElementTree as ET

if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class ConvertEngine:
    def __init__(self, target_rom_dir, firehose_path=None, eng_rom_dir=None, output_dir=None, target_region="tw", use_hardlinks=True, log_cb=None):
        self.target_rom = os.path.abspath(target_rom_dir)
        self.firehose = os.path.abspath(firehose_path) if firehose_path else None
        self.eng_rom = os.path.abspath(eng_rom_dir) if eng_rom_dir else None
        self.target_region = target_region.lower()
        self.use_hardlinks = use_hardlinks
        self.log_cb = log_cb or print

        # Derive output_dir if not specified
        if not output_dir:
            base_name = os.path.basename(self.target_rom.rstrip("\\/"))
            self.output_dir = os.path.join(os.path.dirname(self.target_rom), f"{base_name}_convert")
        else:
            self.output_dir = os.path.abspath(output_dir)

        self.src_images = os.path.join(self.target_rom, "images")
        self.dst_images = os.path.join(self.output_dir, "images")
        self.dst_fix_ota = os.path.join(self.output_dir, "FIX_OTA")

        # Dynamic template directory resolution (supports PyInstaller --onefile)
        if getattr(sys, 'frozen', False):
            meipass_templates = os.path.join(getattr(sys, '_MEIPASS', ''), "templates")
            exe_templates = os.path.join(os.path.dirname(sys.executable), "templates")
            if os.path.isdir(meipass_templates):
                self.templates_dir = meipass_templates
            elif os.path.isdir(exe_templates):
                self.templates_dir = exe_templates
            else:
                self.templates_dir = meipass_templates
        else:
            self.templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

    def log(self, msg):
        try:
            self.log_cb(msg)
        except UnicodeEncodeError:
            try:
                enc = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
                safe_msg = msg.encode(enc, errors='replace').decode(enc)
                print(safe_msg)
            except Exception:
                pass
        except Exception:
            pass

    def detect_product(self):
        flash_bat = os.path.join(self.target_rom, "flash_all.bat")
        if os.path.isfile(flash_bat):
            with open(flash_bat, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                m = re.search(r'product:\s*([a-zA-Z0-9_]+)', content)
                if m:
                    return m.group(1)
        return "unknown"

    def detect_firehose_target(self):
        candidates = [
            "xbl_s_devprg_ns.melf",
            "prog_firehose_ddr.elf",
            "prog_firehose_lite.elf",
            "prog_ufs_firehose_ddr.elf",
            "prog_emmc_firehose_ddr.elf"
        ]
        for c_name in candidates:
            if os.path.isfile(os.path.join(self.src_images, c_name)):
                return c_name
        return "xbl_s_devprg_ns.melf"

    def find_firehose_in_eng(self):
        if not self.eng_rom or not os.path.isdir(self.eng_rom):
            return None
        candidates = [
            "xbl_s_devprg_ns.melf",
            "prog_firehose_ddr.elf",
            "prog_firehose_lite.elf",
            "prog_ufs_firehose_ddr.elf",
            "prog_emmc_firehose_ddr.elf"
        ]
        search_dirs = [
            os.path.join(self.eng_rom, "images"),
            self.eng_rom
        ]
        for s_dir in search_dirs:
            if os.path.isdir(s_dir):
                for c in candidates:
                    p = os.path.join(s_dir, c)
                    if os.path.isfile(p):
                        return p
        return None

    def patch_gpt_tables(self):
        """
        Vá opconfig -> opcust trong gpt_main0.bin và gpt_backup0.bin,
        tính toán lại mã CRC32 bảng phân vùng và tiêu đề chuẩn GPT.
        Hỗ trợ tự động nhận diện sector size (512 hoặc 4096).
        """
        gpt_main_path = os.path.join(self.src_images, "gpt_main0.bin")
        gpt_backup_path = os.path.join(self.src_images, "gpt_backup0.bin")

        if not os.path.isfile(gpt_main_path) or not os.path.isfile(gpt_backup_path):
            self.log("[*] Không tìm thấy gpt_main0.bin hoặc gpt_backup0.bin. Bỏ qua vá GPT.")
            return False

        with open(gpt_main_path, "rb") as f:
            m = bytearray(f.read())
        with open(gpt_backup_path, "rb") as f:
            b = bytearray(f.read())

        old_name = "opconfig".encode("utf-16le")
        new_name = "opcust\x00\x00".encode("utf-16le")

        if old_name not in m and old_name not in b:
            self.log("[*] Không phát hiện phân vùng opconfig trong GPT. Giữ nguyên GPT gốc.")
            shutil.copy2(gpt_main_path, os.path.join(self.dst_images, "gpt_main0.bin"))
            shutil.copy2(gpt_backup_path, os.path.join(self.dst_images, "gpt_backup0.bin"))
            if os.path.isfile(os.path.join(self.src_images, "gpt_both0.bin")):
                shutil.copy2(os.path.join(self.src_images, "gpt_both0.bin"), os.path.join(self.dst_images, "gpt_both0.bin"))
            return False

        # Thay thế chuỗi tên phân vùng
        m_idx = m.find(old_name)
        if m_idx != -1:
            m[m_idx:m_idx+len(new_name)] = new_name

        b_idx = b.find(old_name)
        if b_idx != -1:
            b[b_idx:b_idx+len(new_name)] = new_name

        # Cập nhật CRC cho Main GPT động
        m_hdr_off = m.find(b"EFI PART")
        if m_hdr_off == -1:
            m_hdr_off = 0x1000

        m_num_parts = struct.unpack_from("<I", m, m_hdr_off + 80)[0]
        m_part_size = struct.unpack_from("<I", m, m_hdr_off + 84)[0]
        m_part_bytes = m_num_parts * m_part_size
        m_part_off = 2 * m_hdr_off  # LBA 2
        m_part_crc = zlib.crc32(m[m_part_off:m_part_off + m_part_bytes]) & 0xffffffff
        struct.pack_into("<I", m, m_hdr_off + 88, m_part_crc)
        struct.pack_into("<I", m, m_hdr_off + 16, 0)
        m_hdr_len = struct.unpack_from("<I", m, m_hdr_off + 12)[0]
        m_hdr_crc = zlib.crc32(m[m_hdr_off:m_hdr_off + m_hdr_len]) & 0xffffffff
        struct.pack_into("<I", m, m_hdr_off + 16, m_hdr_crc)

        # Cập nhật CRC cho Backup GPT động
        b_hdr_off = b.find(b"EFI PART")
        if b_hdr_off == -1:
            b_hdr_off = 0x4000

        b_num_parts = struct.unpack_from("<I", b, b_hdr_off + 80)[0]
        b_part_size = struct.unpack_from("<I", b, b_hdr_off + 84)[0]
        b_part_bytes = b_num_parts * b_part_size
        b_part_crc = zlib.crc32(b[:b_part_bytes]) & 0xffffffff
        struct.pack_into("<I", b, b_hdr_off + 88, b_part_crc)
        struct.pack_into("<I", b, b_hdr_off + 16, 0)
        b_hdr_len = struct.unpack_from("<I", b, b_hdr_off + 12)[0]
        b_hdr_crc = zlib.crc32(b[b_hdr_off:b_hdr_off + b_hdr_len]) & 0xffffffff
        struct.pack_into("<I", b, b_hdr_off + 16, b_hdr_crc)

        # Ghi các file GPT đã vá vào dst_images
        with open(os.path.join(self.dst_images, "gpt_main0.bin"), "wb") as f:
            f.write(m)
        with open(os.path.join(self.dst_images, "gpt_backup0.bin"), "wb") as f:
            f.write(b)
        with open(os.path.join(self.dst_images, "gpt_both0.bin"), "wb") as f:
            f.write(m + b)

        # Sao lưu sang dst_fix_ota để phục vụ nạp lẻ
        with open(os.path.join(self.dst_fix_ota, "gpt_main0.bin"), "wb") as f:
            f.write(m)
        with open(os.path.join(self.dst_fix_ota, "gpt_backup0.bin"), "wb") as f:
            f.write(b)

        self.log("[+] Đã chuyển đổi opconfig -> opcust trong GPT và tính lại toàn bộ mã CRC32 thành công.")
        return True

    def build(self, progress_cb=None):
        self.log("=" * 65)
        self.log("   XIAOMI CONVERT ROM STUDIO - CORE BUILD ENGINE")
        self.log("=" * 65)
        self.log(f"[*] ROM Đích (Target ROM) : {self.target_rom}")

        # Tự động tìm Firehose No-Auth từ ENG ROM nếu người dùng chưa chọn file riêng
        active_firehose = self.firehose
        if not active_firehose or not os.path.isfile(active_firehose):
            eng_fh = self.find_firehose_in_eng()
            if eng_fh:
                active_firehose = eng_fh
                self.log(f"[+] Tự động phát hiện Firehose Loader từ ROM ENG: {active_firehose}")

        self.log(f"[*] Firehose No-Auth      : {active_firehose if active_firehose else 'Không có (Dùng loader gốc)'}")
        self.log(f"[*] ROM ENG (Tham chiếu)  : {self.eng_rom if self.eng_rom else 'Không sử dụng'}")
        self.log(f"[*] Khu vực đích (Region) : {self.target_region.upper()}")
        self.log(f"[*] Thư mục xuất Convert  : {self.output_dir}")

        product = self.detect_product()
        self.log(f"[+] Nhận diện mã thiết bị: {product.upper()}")

        if progress_cb: progress_cb(5)

        # 1. Khởi tạo thư mục
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.dst_images, exist_ok=True)
        os.makedirs(self.dst_fix_ota, exist_ok=True)

        # 2. Sao chép các file gốc ở thư mục root
        self.log("\n[1/6] Sao chép các file cấu hình và kịch bản gốc...")
        for fname in os.listdir(self.target_rom):
            fpath = os.path.join(self.target_rom, fname)
            if os.path.isfile(fpath) and not fname.startswith("flash_all"):
                shutil.copy2(fpath, os.path.join(self.output_dir, fname))

        # Sao chép flash_all.bat gốc nếu có
        flash_all_src = os.path.join(self.target_rom, "flash_all.bat")
        flash_all_dst = os.path.join(self.output_dir, "flash_all.bat")
        if os.path.isfile(flash_all_src):
            shutil.copy2(flash_all_src, flash_all_dst)
        self.log("[+] Đã sao chép kịch bản flash gốc (Mặc định Xóa sạch dữ liệu / Clean Flash).")

        if progress_cb: progress_cb(20)

        # 3. Sao chép và Hardlink các phân vùng ảnh trong images
        self.log("\n[2/6] Xử lý các phân vùng ảnh (Tối ưu tốc độ bằng HardLink)...")
        skip_files = {
            "xbl_s_devprg_ns.melf",
            "prog_firehose_ddr.elf",
            "prog_firehose_lite.elf",
            "prog_ufs_firehose_ddr.elf",
            "prog_emmc_firehose_ddr.elf",
            "gpt_main0.bin",
            "gpt_backup0.bin",
            "gpt_both0.bin",
            "rawprogram0.xml",
            "rawprogram1.xml",
            "rawprogram2.xml",
            "rawprogram3.xml",
            "rawprogram4.xml",
            "rawprogram5.xml",
        }

        for fname in os.listdir(self.src_images):
            if fname in skip_files or fname.startswith("wipe_rawprogram_PHY"):
                continue
            fsrc = os.path.join(self.src_images, fname)
            if not os.path.isfile(fsrc):
                continue
            fdst = os.path.join(self.dst_images, fname)
            if os.path.exists(fdst):
                try: os.remove(fdst)
                except Exception: pass

            sz = os.path.getsize(fsrc)
            # Với file lớn (>32MB), ưu tiên dùng HardLink để tạo ROM trong 3 giây
            if self.use_hardlinks and sz > 33554432:
                try:
                    os.link(fsrc, fdst)
                except Exception:
                    shutil.copy2(fsrc, fdst)
            else:
                shutil.copy2(fsrc, fdst)

        # Sao chép các file patch0..5.xml
        for i in range(6):
            pf = f"patch{i}.xml"
            src_pf = os.path.join(self.src_images, pf)
            if os.path.isfile(src_pf):
                shutil.copy2(src_pf, os.path.join(self.dst_images, pf))

        self.log("[+] Hoàn thành sao chép/liên kết toàn bộ các phân vùng gốc.")

        if progress_cb: progress_cb(45)

        # 4. Vá bảng phân vùng GPT
        self.log("\n[3/6] Phân tích và Vá bảng phân vùng GPT (Hardware Carrier Patch)...")
        self.patch_gpt_tables()

        if progress_cb: progress_cb(60)

        # 5. Thay thế Firehose No-Auth
        self.log("\n[4/6] Nhúng Firehose No-Auth (Vượt quyền EDL 9008)...")
        if active_firehose and os.path.isfile(active_firehose):
            target_loader_name = self.detect_firehose_target()
            dest_loader = os.path.join(self.dst_images, target_loader_name)
            shutil.copy2(active_firehose, dest_loader)
            self.log(f"[+] Đã nhúng Firehose No-Auth -> {target_loader_name}")
        else:
            self.log("[!] Cảnh báo: Không có file Firehose No-Auth. Giữ nguyên loader gốc.")

        # 6. Tích hợp opcust.img và misc.img
        self.log("\n[5/6] Tích hợp phân vùng Carrier (opcust.img & misc.img)...")
        selected_opcust = "opcust_tw.img" if self.target_region == "tw" else "opcust_global.img"
        src_opcust_tpl = os.path.join(self.templates_dir, selected_opcust)
        if os.path.isfile(src_opcust_tpl):
            shutil.copy2(src_opcust_tpl, os.path.join(self.dst_images, "opcust.img"))
            shutil.copy2(src_opcust_tpl, os.path.join(self.dst_fix_ota, "opcust.img"))
            self.log(f"[+] Đã tạo opcust.img 20MB chuẩn ext4 theo khu vực: {self.target_region.upper()}")
        else:
            self.log(f"[!] Cảnh báo: Không tìm thấy file template {selected_opcust} tại {self.templates_dir}")

        src_misc_tpl = os.path.join(self.templates_dir, "misc.img")
        if os.path.isfile(src_misc_tpl):
            shutil.copy2(src_misc_tpl, os.path.join(self.dst_images, "misc.img"))
            shutil.copy2(src_misc_tpl, os.path.join(self.dst_fix_ota, "misc.img"))

        if progress_cb: progress_cb(80)

        # 7. Đồng bộ Slot A/B và cập nhật bản đồ rawprogram0..5.xml
        self.log("\n[6/6] Đồng bộ phân vùng Slot A/B và bảo vệ phân vùng Persist...")
        a_map = {}
        for i in [0, 1, 4]:
            rp_path = os.path.join(self.src_images, f"rawprogram{i}.xml")
            if os.path.isfile(rp_path):
                tree = ET.parse(rp_path)
                for prog in tree.getroot().findall("program"):
                    lbl = prog.get("label", "")
                    fn = prog.get("filename", "")
                    if lbl.endswith("_a") and fn:
                        a_map[lbl[:-2]] = fn

        self.log(f"[+] Tìm thấy {len(a_map)} phân vùng Slot A cần đồng bộ sang Slot B.")

        # Copy rawprogram1, 3, 5 nếu có
        for i in [1, 3, 5]:
            src_rp = os.path.join(self.src_images, f"rawprogram{i}.xml")
            if os.path.isfile(src_rp):
                shutil.copy2(src_rp, os.path.join(self.dst_images, f"rawprogram{i}.xml"))

        # Xử lý rawprogram2.xml (Sync Slot B)
        rp2_src = os.path.join(self.src_images, "rawprogram2.xml")
        if os.path.isfile(rp2_src):
            with open(rp2_src, "r", encoding="utf-8") as f:
                rp2_lines = f.readlines()
            new_rp2 = []
            for line in rp2_lines:
                m = re.search(r'label="([^"]+)_b"', line)
                if m and m.group(1) in a_map:
                    fn = a_map[m.group(1)]
                    line = line.replace('filename=""', f'filename="{fn}"')
                new_rp2.append(line)
            with open(os.path.join(self.dst_images, "rawprogram2.xml"), "wb") as f:
                f.write("".join(new_rp2).encode("utf-8"))
            self.log("[+] Đã đồng bộ Slot B trên rawprogram2.xml.")

        # Xử lý rawprogram4.xml (Sync Slot B + Bảo vệ persist)
        rp4_src = os.path.join(self.src_images, "rawprogram4.xml")
        if os.path.isfile(rp4_src):
            with open(rp4_src, "r", encoding="utf-8") as f:
                rp4_lines = f.readlines()
            new_rp4 = []
            for line in rp4_lines:
                if 'label="persist"' in line:
                    line = line.replace('filename="persist.img"', 'filename=""')
                m = re.search(r'label="([^"]+)_b"', line)
                if m and m.group(1) in a_map:
                    fn = a_map[m.group(1)]
                    line = line.replace('filename=""', f'filename="{fn}"')
                new_rp4.append(line)
            with open(os.path.join(self.dst_images, "rawprogram4.xml"), "wb") as f:
                f.write("".join(new_rp4).encode("utf-8"))
            with open(os.path.join(self.dst_images, "rawprogram4_KEEP_PERSIST.xml"), "wb") as f:
                f.write("".join(new_rp4).encode("utf-8"))
            self.log("[+] Đã cập nhật rawprogram4.xml (Đồng bộ Slot B & Bảo vệ persist an toàn 100%).")

        # Xử lý rawprogram0.xml: Gán opcust, misc, vbmeta_system_b, tạo KEEP_DATA vs CLEAN_FLASH
        rp0_src = os.path.join(self.src_images, "rawprogram0.xml")
        if os.path.isfile(rp0_src):
            with open(rp0_src, "r", encoding="utf-8") as f:
                rp0_lines = f.readlines()

            def build_rp0_custom(keep_data=True):
                out = []
                for line in rp0_lines:
                    if 'label="opconfig"' in line or 'label="opcust"' in line:
                        line = line.replace('label="opconfig"', 'label="opcust"')
                        line = line.replace('filename=""', 'filename="opcust.img"')
                        line = line.replace('sparse="true"', 'sparse="false"')
                    elif 'label="misc"' in line:
                        line = line.replace('filename=""', 'filename="misc.img"')
                    elif 'label="vbmeta_system_b"' in line:
                        line = line.replace('filename=""', 'filename="vbmeta_system.img"')
                    elif 'label="userdata"' in line:
                        if keep_data:
                            line = line.replace('filename="userdata.img"', 'filename=""')
                            line = line.replace('sparse="true"', 'sparse="false"')
                        else:
                            line = line.replace('filename=""', 'filename="userdata.img"')
                            line = line.replace('sparse="false"', 'sparse="true"')
                    out.append(line)
                return "".join(out).encode("utf-8")

            rp0_keep = build_rp0_custom(keep_data=True)
            rp0_clean = build_rp0_custom(keep_data=False)

            with open(os.path.join(self.dst_images, "rawprogram0.xml"), "wb") as f:
                f.write(rp0_clean)  # Mặc định: XÓA DỮ LIỆU (Clean Flash)
            with open(os.path.join(self.dst_images, "rawprogram0_CLEAN_FLASH.xml"), "wb") as f:
                f.write(rp0_clean)
            with open(os.path.join(self.dst_images, "rawprogram0_clean.xml.bak"), "wb") as f:
                f.write(rp0_clean)

            # Tạo file FIX_OTA/rawprogram0_CHI_NAP_FIX_OTA.xml
            fix_ota_lines = ['<?xml version="1.0" ?>\r\n<data>\r\n']
            for line in rp0_clean.decode("utf-8").splitlines():
                if any(x in line for x in ['label="misc"', 'label="opcust"', 'label="PrimaryGPT"', 'label="BackupGPT"']):
                    fix_ota_lines.append(f"  {line.strip()}\r\n")
            fix_ota_lines.append("</data>\r\n")
            with open(os.path.join(self.dst_fix_ota, "rawprogram0_CHI_NAP_FIX_OTA.xml"), "wb") as f:
                f.write("".join(fix_ota_lines).encode("utf-8"))

            self.log("[+] Đã tạo rawprogram0.xml (Mặc định Xóa sạch dữ liệu / Clean Flash) & Gói nạp lẻ FIX_OTA.")

        if progress_cb: progress_cb(100)

        self.log("\n" + "=" * 65)
        self.log(">>> XUẤT BẢN ROM CONVERT THÀNH CÔNG RỰC RỠ 100%! <<<")
        self.log(f"Đường dẫn ROM hoàn chỉnh: {self.output_dir}")
        self.log("=" * 65)
        return True, self.output_dir
