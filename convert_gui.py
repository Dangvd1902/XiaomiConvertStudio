import sys
import os
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QProgressBar, QTextEdit,
    QGroupBox, QMessageBox, QGridLayout, QFrame, QComboBox, QCheckBox, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import convert_core

STYLESHEET = """
QMainWindow {
    background-color: #181825;
}
QWidget {
    color: #cdd6f4;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45475a;
    color: #ffffff;
}
QPushButton#primaryBtn {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
    font-size: 14px;
    font-weight: bold;
}
QPushButton#primaryBtn:hover {
    background-color: #b4befe;
}
QPushButton#successBtn {
    background-color: #a6e3a1;
    color: #11111b;
    border: none;
}
QPushButton#successBtn:hover {
    background-color: #94e2d5;
}
QLineEdit {
    background-color: #11111b;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QComboBox {
    background-color: #11111b;
    color: #fab387;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QCheckBox {
    color: #a6adc8;
}
QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-radius: 3px;
}
QProgressBar {
    border: 1px solid #313244;
    border-radius: 6px;
    text-align: center;
    background-color: #11111b;
    color: #ffffff;
    font-weight: bold;
    height: 22px;
}
QProgressBar::chunk {
    background-color: #a6e3a1;
    border-radius: 5px;
}
QTextEdit {
    background-color: #11111b;
    color: #a6e3a1;
    border: 1px solid #313244;
    border-radius: 6px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}
QLabel#headerTitle {
    font-size: 18px;
    font-weight: bold;
    color: #89b4fa;
}
QLabel#headerSub {
    font-size: 12px;
    color: #a6adc8;
}
"""

class BuildWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, target_rom, firehose, eng_rom, output_dir, region, use_hardlink):
        super().__init__()
        self.target_rom = target_rom
        self.firehose = firehose
        self.eng_rom = eng_rom
        self.output_dir = output_dir
        self.region = region
        self.use_hardlink = use_hardlink

    def run(self):
        try:
            engine = convert_core.ConvertEngine(
                target_rom_dir=self.target_rom,
                firehose_path=self.firehose,
                eng_rom_dir=self.eng_rom,
                output_dir=self.output_dir,
                target_region=self.region,
                use_hardlinks=self.use_hardlink,
                log_cb=self.log_signal.emit
            )
            success, out_path = engine.build(progress_cb=self.progress_signal.emit)
            self.finished_signal.emit(success, out_path)
        except Exception as e:
            self.log_signal.emit(f"[!] Lỗi nghiêm trọng: {str(e)}")
            self.finished_signal.emit(False, str(e))

class ConvertMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xiaomi Convert ROM Studio (X-Convert)")
        self.resize(920, 750)
        self.setStyleSheet(STYLESHEET)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Header
        header_frame = QFrame()
        header_lay = QVBoxLayout(header_frame)
        header_lay.setContentsMargins(0, 0, 0, 5)
        title = QLabel("XIAOMI CONVERT ROM STUDIO - CHUYÊN DỤNG")
        title.setObjectName("headerTitle")
        sub = QLabel("Tạo bản ROM Convert Quốc tế / Taiwan tự động từ ROM Gốc, ROM ENG & Firehose No-Auth")
        sub.setObjectName("headerSub")
        header_lay.addWidget(title)
        header_lay.addWidget(sub)
        main_layout.addWidget(header_frame)

        # 1. Input Sources Group
        grp_inputs = QGroupBox("1. Các thành phần đầu vào (Source Files)")
        grid_in = QGridLayout(grp_inputs)
        grid_in.setSpacing(8)

        # Target ROM
        grid_in.addWidget(QLabel("Thư mục ROM Đích (Target Fastboot):"), 0, 0)
        self.txt_target_rom = QLineEdit()
        self.txt_target_rom.setPlaceholderText("Chọn thư mục ROM Fastboot Quốc tế / Taiwan (VD: vermeer_tw_global_images...)")
        self.txt_target_rom.textChanged.connect(self.auto_update_output_path)
        btn_br_target = QPushButton("📁 Duyệt thư mục...")
        btn_br_target.clicked.connect(self.browse_target_rom)
        grid_in.addWidget(self.txt_target_rom, 0, 1)
        grid_in.addWidget(btn_br_target, 0, 2)

        # Firehose No-Auth
        grid_in.addWidget(QLabel("File Firehose No-Auth (.elf/.melf):"), 1, 0)
        self.txt_firehose = QLineEdit()
        self.txt_firehose.setPlaceholderText("Chọn file firehose no-auth (VD: xiaomi_8550_firehose_noauth.melf)")
        btn_br_fh = QPushButton("📄 Chọn file...")
        btn_br_fh.clicked.connect(self.browse_firehose)
        grid_in.addWidget(self.txt_firehose, 1, 1)
        grid_in.addWidget(btn_br_fh, 1, 2)

        # ENG ROM (Optional)
        grid_in.addWidget(QLabel("Thư mục ROM ENG (Tùy chọn):"), 2, 0)
        self.txt_eng_rom = QLineEdit()
        self.txt_eng_rom.setPlaceholderText("Chọn thư mục ROM Factory ENG nếu có (để đối chiếu phân vùng)")
        btn_br_eng = QPushButton("📁 Duyệt thư mục...")
        btn_br_eng.clicked.connect(self.browse_eng_rom)
        grid_in.addWidget(self.txt_eng_rom, 2, 1)
        grid_in.addWidget(btn_br_eng, 2, 2)

        # Output Dir
        grid_in.addWidget(QLabel("Thư mục xuất Convert ROM:"), 3, 0)
        self.txt_output_dir = QLineEdit()
        btn_br_out = QPushButton("📁 Đổi nơi lưu...")
        btn_br_out.clicked.connect(self.browse_output_dir)
        grid_in.addWidget(self.txt_output_dir, 3, 1)
        grid_in.addWidget(btn_br_out, 3, 2)

        main_layout.addWidget(grp_inputs)

        # 2. Options Group
        grp_opts = QGroupBox("2. Tùy chọn cấu hình Convert")
        grid_opts = QGridLayout(grp_opts)

        grid_opts.addWidget(QLabel("Khu vực chuyển đổi (Target Region):"), 0, 0)
        self.cb_region = QComboBox()
        self.cb_region.addItem("🇹🇼 Đài Loan (Taiwan - tw) [Khuyên dùng: Ghi âm cuộc gọi không báo]", "tw")
        self.cb_region.addItem("🌐 Quốc tế (Global - Global)", "global")
        self.cb_region.addItem("🇪🇺 Châu Âu (EEA - eea)", "eea")
        self.cb_region.addItem("🇮🇳 Ấn Độ (India - in)", "in")
        grid_opts.addWidget(self.cb_region, 0, 1)

        self.chk_gpt = QCheckBox("Tự động vá bảng GPT (opconfig -> opcust) & tính lại toàn bộ mã CRC32")
        self.chk_gpt.setChecked(True)
        grid_opts.addWidget(self.chk_gpt, 1, 0, 1, 2)

        self.chk_slot = QCheckBox("Đồng bộ phân vùng Slot A sang Slot B (Chống brick khi cập nhật OTA chuyển Slot)")
        self.chk_slot.setChecked(True)
        grid_opts.addWidget(self.chk_slot, 2, 0, 1, 2)

        self.chk_persist = QCheckBox("Bảo vệ an toàn tuyệt đối phân vùng Persist & EFS (Giữ IMEI, Vân tay, Cảm biến)")
        self.chk_persist.setChecked(True)
        grid_opts.addWidget(self.chk_persist, 3, 0, 1, 2)

        self.chk_hardlink = QCheckBox("Tối ưu tốc độ Build siêu tốc bằng HardLink (Tạo ROM 15GB chỉ mất 3-5 giây)")
        self.chk_hardlink.setChecked(True)
        grid_opts.addWidget(self.chk_hardlink, 4, 0, 1, 2)

        main_layout.addWidget(grp_opts)

        # 3. Action Group
        grp_act = QGroupBox("3. Tiến hành tạo ROM Convert")
        lay_act = QVBoxLayout(grp_act)

        self.prog_bar = QProgressBar()
        self.prog_bar.setValue(0)
        lay_act.addWidget(self.prog_bar)

        lay_act_btns = QHBoxLayout()
        self.btn_build = QPushButton("🚀 BẮT ĐẦU TẠO ROM CONVERT (1-CLICK)")
        self.btn_build.setObjectName("primaryBtn")
        self.btn_build.setFixedHeight(42)
        self.btn_build.clicked.connect(self.start_build)
        lay_act_btns.addWidget(self.btn_build, 2)

        self.btn_open_folder = QPushButton("📂 Mở thư mục ROM đã tạo")
        self.btn_open_folder.setObjectName("successBtn")
        self.btn_open_folder.setFixedHeight(42)
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_output_folder)
        lay_act_btns.addWidget(self.btn_open_folder, 1)

        lay_act.addLayout(lay_act_btns)
        main_layout.addWidget(grp_act)

        # 4. Live Logs Terminal
        grp_log = QGroupBox("4. Nhật ký xử lý thời gian thực (Live Build Logs)")
        lay_log = QVBoxLayout(grp_log)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        lay_log.addWidget(self.txt_log)
        main_layout.addWidget(grp_log)

        self.log("[+] Chào mừng đến với Xiaomi Convert ROM Studio.")
        self.log("[+] Vui lòng chọn Thư mục ROM Đích và file Firehose No-Auth để bắt đầu.")

        # Tự động điền nếu phát hiện các file sẵn có trong C:\Romconvert
        self.auto_detect_defaults()

    def log(self, text):
        self.txt_log.append(text)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def auto_detect_defaults(self):
        default_rom = r"C:\Romconvert\vermeer_tw_global_images_OS3.0.302.0.WNKTWXM_16.0"
        if os.path.isdir(default_rom):
            self.txt_target_rom.setText(default_rom)

        default_fh = r"C:\Romconvert\xiaomi_8550_firehose_noauth.melf"
        if os.path.isfile(default_fh):
            self.txt_firehose.setText(default_fh)

        default_eng = r"C:\Romconvert\EDL_K70_ENG"
        if os.path.isdir(default_eng):
            self.txt_eng_rom.setText(default_eng)

    def auto_update_output_path(self):
        t_path = self.txt_target_rom.text().strip('\"\' ')
        if t_path and os.path.isdir(t_path):
            base = os.path.basename(t_path.rstrip("\\/"))
            out = os.path.join(os.path.dirname(t_path), f"{base}_convert")
            self.txt_output_dir.setText(out)

    def browse_target_rom(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục ROM Fastboot Đích")
        if d:
            self.txt_target_rom.setText(d)

    def browse_firehose(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn file Firehose No-Auth", "", "Firehose (*.elf *.melf *.bin *.mbn)")
        if f:
            self.txt_firehose.setText(f)

    def browse_eng_rom(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục ROM Factory ENG (Nếu có)")
        if d:
            self.txt_eng_rom.setText(d)
            if not self.txt_firehose.text().strip():
                candidates = ["xbl_s_devprg_ns.melf", "prog_firehose_ddr.elf", "prog_firehose_lite.elf", "prog_ufs_firehose_ddr.elf"]
                for sub in ["images", ""]:
                    search_dir = os.path.join(d, sub) if sub else d
                    if os.path.isdir(search_dir):
                        for c in candidates:
                            fp = os.path.join(search_dir, c)
                            if os.path.isfile(fp):
                                self.txt_firehose.setText(fp)
                                self.log(f"[+] Tự động phát hiện Firehose từ ROM ENG: {fp}")
                                break

    def browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất Convert ROM")
        if d:
            self.txt_output_dir.setText(d)

    def start_build(self):
        target_rom = self.txt_target_rom.text().strip('\"\' ')
        firehose = self.txt_firehose.text().strip('\"\' ')
        eng_rom = self.txt_eng_rom.text().strip('\"\' ')
        output_dir = self.txt_output_dir.text().strip('\"\' ')
        region = self.cb_region.currentData()
        use_hardlink = self.chk_hardlink.isChecked()

        if not target_rom or not os.path.isdir(target_rom):
            QMessageBox.warning(self, "Thiếu dữ liệu", "Vui lòng chọn Thư mục ROM Đích hợp lệ!")
            return
        if not os.path.isdir(os.path.join(target_rom, "images")):
            QMessageBox.warning(self, "Lỗi cấu trúc ROM", "Thư mục ROM Đích phải chứa thư mục 'images' bên trong!")
            return

        self.btn_build.setEnabled(False)
        self.btn_open_folder.setEnabled(False)
        self.prog_bar.setValue(0)
        self.last_output = output_dir

        self.worker = BuildWorker(target_rom, firehose, eng_rom, output_dir, region, use_hardlink)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.prog_bar.setValue)
        self.worker.finished_signal.connect(self.on_build_finished)
        self.worker.start()

    def on_build_finished(self, success, result_msg):
        self.btn_build.setEnabled(True)
        if success:
            self.btn_open_folder.setEnabled(True)
            self.last_output = result_msg
            QMessageBox.information(self, "Thành công!", f"Đã tạo Convert ROM hoàn tất!\n\nĐịa chỉ: {result_msg}")
        else:
            QMessageBox.critical(self, "Thất bại", f"Đã xảy ra lỗi trong quá trình tạo ROM:\n\n{result_msg}")

    def open_output_folder(self):
        if hasattr(self, 'last_output') and os.path.isdir(self.last_output):
            subprocess.run(["explorer", self.last_output])

def main():
    app = QApplication(sys.argv)
    win = ConvertMainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
