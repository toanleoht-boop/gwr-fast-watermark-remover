import sys
import os
import subprocess
import qdarktheme
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox, QFrame,
    QSizePolicy, QComboBox, QGroupBox, QDoubleSpinBox, QRadioButton, QButtonGroup,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QSplitter,
    QDialog, QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt, QSize, QSizeF, QPointF, QRectF, pyqtSignal, QEvent
from PyQt6.QtGui import QPixmap, QIcon, QFont, QPainter, QPen, QColor, QBrush, QImage, QMouseEvent

from worker import WatermarkWorker

SUPPORTED_EXTS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.mp4', '.webm', '.mov', '.avi', '.mkv']

POSITION_PRESETS = {
    "Góc Dưới - Phải (Bottom-Right)": (85.0, 85.0, 12.0, 12.0),
    "Góc Dưới - Trái (Bottom-Left)": (3.0, 85.0, 12.0, 12.0),
    "Góc Trên - Phải (Top-Right)": (85.0, 3.0, 12.0, 12.0),
    "Góc Trên - Trái (Top-Left)": (3.0, 3.0, 12.0, 12.0),
    "Thanh viền dưới (Bottom Bar)": (0.0, 92.0, 100.0, 8.0),
    "Tùy chỉnh Tọa độ %": None
}

MODERN_STYLE_SHEET = """
QMainWindow {
    background-color: #0B0E14;
}
QWidget {
    color: #E2E8F0;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
}
QGroupBox {
    background-color: #151B26;
    border: 1px solid #232D3F;
    border-radius: 12px;
    margin-top: 8px;
    padding: 14px;
    font-weight: bold;
    font-size: 13px;
    color: #38BDF8;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: #38BDF8;
}
QRadioButton {
    font-size: 13px;
    color: #F1F5F9;
    padding: 6px;
    spacing: 8px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #64748B;
}
QRadioButton::indicator:checked {
    border: 2px solid #8B5CF6;
    background-color: #8B5CF6;
}
QPushButton {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    color: #F8FAFC;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 14px;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #6366F1;
}
QPushButton:pressed {
    background-color: #0F172A;
}
QPushButton#btn_primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7C3AED, stop:1 #4F46E5);
    border: none;
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 700;
    border-radius: 10px;
    padding: 12px 24px;
}
QPushButton#btn_primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #6366F1);
}
QPushButton#btn_primary:disabled {
    background: #334155;
    color: #64748B;
}
QPushButton#btn_accent_purple {
    background-color: #2E1065;
    border: 1px solid #6B21A8;
    color: #E9D5FF;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton#btn_accent_purple:hover {
    background-color: #581C87;
}
QPushButton#btn_accent_emerald {
    background-color: #064E3B;
    border: 1px solid #047857;
    color: #A7F3D0;
    border-radius: 8px;
    font-weight: 600;
}
QPushButton#btn_accent_emerald:hover {
    background-color: #047857;
}
QComboBox, QDoubleSpinBox {
    background-color: #0F172A;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #F8FAFC;
    padding: 5px 8px;
    font-size: 12px;
}
QComboBox:hover, QDoubleSpinBox:hover {
    border-color: #8B5CF6;
}
QProgressBar {
    background-color: #1E293B;
    border-radius: 8px;
    text-align: center;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 12px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #06B6D4);
    border-radius: 8px;
}
"""

def extract_video_first_frame(video_path):
    try:
        temp_dir = None
        target_path = video_path
        if any(ord(c) > 127 for c in video_path):
            import tempfile, shutil
            temp_dir = tempfile.mkdtemp()
            ext = os.path.splitext(video_path)[1] or ".mp4"
            target_path = os.path.join(temp_dir, f"preview_temp{ext}")
            shutil.copy2(video_path, target_path)

        cap = cv2.VideoCapture(target_path)
        if not cap.isOpened():
            if temp_dir: shutil.rmtree(temp_dir, ignore_errors=True)
            return None
            
        ret, frame = cap.read()
        cap.release()
        if temp_dir: shutil.rmtree(temp_dir, ignore_errors=True)

        if ret and frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg.copy())
    except Exception as e:
        print("Video preview extraction failed:", e)
    return None

class ZoomableGraphicsView(QGraphicsView):
    roi_selected = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)

        self.roi_rect_item = QGraphicsRectItem()
        self.roi_rect_item.setPen(QPen(QColor(239, 68, 68), 2, Qt.PenStyle.DashLine))
        self.roi_rect_item.setBrush(QBrush(QColor(239, 68, 68, 70)))
        self.scene.addItem(self.roi_rect_item)
        self.roi_rect_item.hide()

        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.setStyleSheet("QGraphicsView { border: 2px dashed #334155; border-radius: 14px; background: #0F172A; }")

        self.is_drawing = False
        self.is_right_panning = False
        self.last_right_pos = None
        self.start_scene_pos = QPointF()
        self.current_mode = 'select'

        self.setAcceptDrops(True)

    def set_current_pixmap(self, pixmap):
        self.pixmap_item.setPixmap(pixmap)
        if not pixmap.isNull():
            self.scene.setSceneRect(QRectF(pixmap.rect()))
            self.reset_zoom()
        else:
            self.scene.setSceneRect(QRectF(0, 0, 400, 300))
        self.roi_rect_item.hide()

    def reset_zoom(self):
        if not self.pixmap_item.pixmap().isNull():
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        if not self.pixmap_item.pixmap().isNull():
            self.scale(1.25, 1.25)

    def zoom_out(self):
        if not self.pixmap_item.pixmap().isNull():
            self.scale(1.0 / 1.25, 1.0 / 1.25)

    def wheelEvent(self, event):
        if not self.pixmap_item.pixmap().isNull():
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
            self.scale(zoom_factor, zoom_factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def set_mode(self, mode):
        self.current_mode = mode
        if mode == 'pan':
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def mousePressEvent(self, event):
        if self.current_mode == 'select' and event.button() == Qt.MouseButton.LeftButton:
            if not self.pixmap_item.pixmap().isNull():
                scene_pos = self.mapToScene(event.pos())
                img_rect = QRectF(self.pixmap_item.pixmap().rect())
                if img_rect.contains(scene_pos):
                    self.is_drawing = True
                    self.start_scene_pos = scene_pos
                    self.roi_rect_item.setRect(QRectF(self.start_scene_pos, QSizeF(0.0, 0.0)))
                    self.roi_rect_item.show()
                    event.accept()
                    return
        elif event.button() == Qt.MouseButton.RightButton:
            self.is_right_panning = True
            self.last_right_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_right_panning and self.last_right_pos is not None:
            delta = event.pos() - self.last_right_pos
            self.last_right_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        elif self.is_drawing:
            curr_scene_pos = self.mapToScene(event.pos())
            rect = QRectF(self.start_scene_pos, curr_scene_pos).normalized()
            img_rect = QRectF(self.pixmap_item.pixmap().rect())
            rect = rect.intersected(img_rect)
            self.roi_rect_item.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and self.is_right_panning:
            self.is_right_panning = False
            self.last_right_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        elif self.is_drawing and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            rect = self.roi_rect_item.rect()
            img_rect = QRectF(self.pixmap_item.pixmap().rect())
            
            if rect.width() > 5 and rect.height() > 5 and not img_rect.isEmpty():
                pw, ph = img_rect.width(), img_rect.height()
                x_pct = (rect.x() / pw) * 100.0
                y_pct = (rect.y() / ph) * 100.0
                w_pct = (rect.width() / pw) * 100.0
                h_pct = (rect.height() / ph) * 100.0

                self.roi_selected.emit(x_pct, y_pct, w_pct, h_pct)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                self.window().load_inputs(paths)

class AudioFixDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Khôi Phục Âm Thanh Gốc")
        self.setMinimumWidth(550)
        self.setStyleSheet(MODERN_STYLE_SHEET)

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        
        self.orig_edit = QLineEdit()
        self.orig_btn = QPushButton("Chọn...")
        self.orig_btn.clicked.connect(lambda: self.browse_dir(self.orig_edit))
        row1 = QHBoxLayout()
        row1.addWidget(self.orig_edit)
        row1.addWidget(self.orig_btn)
        form_layout.addRow("1. Thư mục Video Gốc:", row1)

        self.clean_edit = QLineEdit()
        self.clean_btn = QPushButton("Chọn...")
        self.clean_btn.clicked.connect(lambda: self.browse_dir(self.clean_edit))
        row2 = QHBoxLayout()
        row2.addWidget(self.clean_edit)
        row2.addWidget(self.clean_btn)
        form_layout.addRow("2. Thư mục Đã Xóa Logo:", row2)

        self.out_edit = QLineEdit()
        self.out_btn = QPushButton("Chọn...")
        self.out_btn.clicked.connect(lambda: self.browse_dir(self.out_edit))
        row3 = QHBoxLayout()
        row3.addWidget(self.out_edit)
        row3.addWidget(self.out_btn)
        form_layout.addRow("3. Thư mục Output Mới:", row3)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("BẮT ĐẦU GHÉP TIẾNG")
        self.start_btn.setObjectName("btn_accent_purple")
        self.start_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

    def browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục")
        if d:
            line_edit.setText(d)

class VideoTrimDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cắt Video Hàng Loạt")
        self.setMinimumWidth(550)
        self.setStyleSheet(MODERN_STYLE_SHEET)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.input_edit = QLineEdit()
        self.input_btn = QPushButton("Chọn...")
        self.input_btn.clicked.connect(lambda: self.browse_dir(self.input_edit))
        row1 = QHBoxLayout()
        row1.addWidget(self.input_edit)
        row1.addWidget(self.input_btn)
        form_layout.addRow("1. Thư mục Video Gốc:", row1)

        self.out_edit = QLineEdit()
        self.out_btn = QPushButton("Chọn...")
        self.out_btn.clicked.connect(lambda: self.browse_dir(self.out_edit))
        row2 = QHBoxLayout()
        row2.addWidget(self.out_edit)
        row2.addWidget(self.out_btn)
        form_layout.addRow("2. Thư mục Output:", row2)

        from PyQt6.QtWidgets import QSpinBox
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)
        self.duration_spin.setValue(6)
        self.duration_spin.setSuffix(" giây")
        form_layout.addRow("3. Độ dài muốn cắt (giây):", self.duration_spin)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("BẮT ĐẦU CẮT")
        self.start_btn.setObjectName("btn_accent_purple")
        self.start_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)
        layout.addLayout(btn_layout)

    def browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục")
        if d:
            line_edit.setText(d)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GWR Fast Watermark Remover")
        self.setMinimumSize(1080, 780)
        self.input_paths = []
        self.output_dir = None
        self.worker = None

        self.setAcceptDrops(True)

        self.setup_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            paths = [url.toLocalFile() for url in urls if url.isLocalFile()]
            if paths:
                self.load_inputs(paths)

    def setup_ui(self):
        self.setStyleSheet(MODERN_STYLE_SHEET)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(10)

        # Header Bar
        header_bar = QHBoxLayout()
        
        brand_label = QLabel("✨ GWR FAST WATERMARK REMOVER")
        brand_font = brand_label.font()
        brand_font.setPointSize(17)
        brand_font.setBold(True)
        brand_label.setFont(brand_font)
        brand_label.setStyleSheet("color: #F8FAFC; letter-spacing: 1px;")

        badge_sub = QLabel("ẢNH & VIDEO HÀNG LOẠT")
        badge_sub.setStyleSheet("background: #1E1B4B; color: #A7F3D0; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px; border: 1px solid #059669;")

        header_bar.addWidget(brand_label)
        header_bar.addWidget(badge_sub)
        header_bar.addStretch()

        self.btn_trim_video = QPushButton("✂️ Cắt Video Hàng Loạt")
        self.btn_trim_video.setObjectName("btn_accent_purple")
        self.btn_trim_video.clicked.connect(self.run_video_trim_tool)

        self.btn_fix_audio = QPushButton("🎵 Khôi Phục Âm Thanh Gốc")
        self.btn_fix_audio.setObjectName("btn_accent_purple")
        self.btn_fix_audio.clicked.connect(self.run_audio_fix_tool)

        self.open_out_btn = QPushButton("📂 Thư Mục Kết Quả")
        self.open_out_btn.setObjectName("btn_accent_emerald")
        self.open_out_btn.clicked.connect(self.open_output_dir)

        header_bar.addWidget(self.btn_trim_video)
        header_bar.addWidget(self.btn_fix_audio)
        header_bar.addWidget(self.open_out_btn)
        self.btn_trim_video.hide()
        self.btn_fix_audio.hide()
        main_layout.addLayout(header_bar)
        subtitle = QLabel("Xóa watermark cố định nhanh · Tự nhận diện · Giữ nguyên âm thanh · Xử lý hàng loạt")
        subtitle.setStyleSheet("color:#7C8AA5; font-size:12px; padding:0 2px 8px 2px;")
        main_layout.addWidget(subtitle)

        # Splitter Layout (Left Control Sidebar + Right Main Workspace)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter, stretch=1)

        # --- LEFT SIDEBAR PANEL ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 10, 0)
        left_layout.setSpacing(10)

        # Group 1: Engine Selection
        engine_box = QGroupBox("Chế độ xử lý")
        engine_layout = QVBoxLayout(engine_box)

        self.radio_lama = QRadioButton("✨ AI LaMa (Deep Learning - Siêu Nét)")
        self.radio_opencv = QRadioButton("🚀 Smart Fast (khuyến nghị)")
        self.radio_gemini = QRadioButton("⚡ Gemini Auto (Google Engine)")
        self.radio_opencv.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_lama)
        self.mode_group.addButton(self.radio_opencv)
        self.mode_group.addButton(self.radio_gemini)
        
        self.radio_lama.toggled.connect(self.on_mode_changed)
        self.radio_opencv.toggled.connect(self.on_mode_changed)

        engine_layout.addWidget(self.radio_lama)
        engine_layout.addWidget(self.radio_opencv)
        engine_layout.addWidget(self.radio_gemini)
        self.radio_lama.hide()
        self.radio_gemini.hide()
        left_layout.addWidget(engine_box)

        # Group 2: Position & Coordinates
        self.custom_pos_widget = QGroupBox("Vị trí Logo / Quét chọn ROI")
        pos_layout = QVBoxLayout(self.custom_pos_widget)

        preset_layout = QHBoxLayout()
        preset_label = QLabel("Preset:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(POSITION_PRESETS.keys()))
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo, stretch=1)
        pos_layout.addLayout(preset_layout)

        coord_grid = QHBoxLayout()
        self.spin_x = QDoubleSpinBox()
        self.spin_x.setPrefix("X: ")
        self.spin_x.setSuffix("%")
        self.spin_x.setRange(0, 100)
        self.spin_x.setValue(85.0)

        self.spin_y = QDoubleSpinBox()
        self.spin_y.setPrefix("Y: ")
        self.spin_y.setSuffix("%")
        self.spin_y.setRange(0, 100)
        self.spin_y.setValue(85.0)

        coord_grid.addWidget(self.spin_x)
        coord_grid.addWidget(self.spin_y)
        pos_layout.addLayout(coord_grid)

        coord_grid2 = QHBoxLayout()
        self.spin_w = QDoubleSpinBox()
        self.spin_w.setPrefix("W: ")
        self.spin_w.setSuffix("%")
        self.spin_w.setRange(1, 100)
        self.spin_w.setValue(12.0)

        self.spin_h = QDoubleSpinBox()
        self.spin_h.setPrefix("H: ")
        self.spin_h.setSuffix("%")
        self.spin_h.setRange(1, 100)
        self.spin_h.setValue(12.0)

        coord_grid2.addWidget(self.spin_w)
        coord_grid2.addWidget(self.spin_h)
        pos_layout.addLayout(coord_grid2)

        left_layout.addWidget(self.custom_pos_widget)

        # Group 3: Input & Output Location Info
        files_box = QGroupBox("Thông tin Đầu vào / Đầu ra")
        files_layout = QVBoxLayout(files_box)

        self.select_files_btn = QPushButton("📁 Chọn File / Thư mục")
        self.select_files_btn.clicked.connect(self.select_files)
        files_layout.addWidget(self.select_files_btn)

        self.auto_detect_btn = QPushButton("🎯 Tự động tìm Logo")
        self.auto_detect_btn.clicked.connect(self.auto_detect_logo)
        self.auto_detect_btn.setEnabled(False)
        files_layout.addWidget(self.auto_detect_btn)

        self.output_label = QLabel("Output mặc định: Template")
        self.output_label.setStyleSheet("color: #94A3B8; font-size: 11px;")
        self.output_label.setWordWrap(True)
        files_layout.addWidget(self.output_label)

        self.select_out_btn = QPushButton("⚙️ Đổi Thư Mục Lưu")
        self.select_out_btn.clicked.connect(self.select_output_dir)
        files_layout.addWidget(self.select_out_btn)

        left_layout.addWidget(files_box)
        left_layout.addStretch()

        splitter.addWidget(left_panel)

        # --- RIGHT WORKSPACE PANEL ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # Canvas Control Toolbar
        view_ctrl_layout = QHBoxLayout()
        
        self.btn_tool_select = QPushButton("📐 Quét Chọn Vùng Xóa")
        self.btn_tool_select.setCheckable(True)
        self.btn_tool_select.setChecked(True)

        self.btn_tool_pan = QPushButton("🖐️ Di Chuyển (Pan)")
        self.btn_tool_pan.setCheckable(True)

        self.tool_group = QButtonGroup(self)
        self.tool_group.addButton(self.btn_tool_select)
        self.tool_group.addButton(self.btn_tool_pan)
        
        self.btn_tool_select.clicked.connect(lambda: self.drop_area.set_mode('select'))
        self.btn_tool_pan.clicked.connect(lambda: self.drop_area.set_mode('pan'))

        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_out = QPushButton("🔍-")
        self.btn_zoom_reset = QPushButton("↺ Fit")

        self.btn_zoom_in.clicked.connect(lambda: self.drop_area.zoom_in())
        self.btn_zoom_out.clicked.connect(lambda: self.drop_area.zoom_out())
        self.btn_zoom_reset.clicked.connect(lambda: self.drop_area.reset_zoom())

        view_ctrl_layout.addWidget(self.btn_tool_select)
        view_ctrl_layout.addWidget(self.btn_tool_pan)
        view_ctrl_layout.addSpacing(10)
        view_ctrl_layout.addWidget(self.btn_zoom_in)
        view_ctrl_layout.addWidget(self.btn_zoom_out)
        view_ctrl_layout.addWidget(self.btn_zoom_reset)
        view_ctrl_layout.addStretch()

        right_layout.addLayout(view_ctrl_layout)

        # Workspace QGraphicsView Drop Area
        self.drop_area = ZoomableGraphicsView()
        self.drop_area.roi_selected.connect(self.on_interactive_roi_selected)
        right_layout.addWidget(self.drop_area, stretch=1)

        # Main Action Button & Progress Bar
        self.process_btn = QPushButton("🚀 BẮT ĐẦU XÓA WATERMARK HÀNG LOẠT")
        self.process_btn.setObjectName("btn_primary")
        self.process_btn.setMinimumHeight(48)
        self.process_btn.clicked.connect(self.process_files)
        self.process_btn.setEnabled(False)
        right_layout.addWidget(self.process_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(22)
        self.progress_bar.hide()
        right_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Kéo thả Ảnh / Video hoặc Thư mục vào khung làm việc ở trên")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #64748B; font-weight: 500;")
        right_layout.addWidget(self.status_label)

        splitter.addWidget(right_panel)

        # Set Splitter ratio (Left 32%, Right 68%)
        splitter.setSizes([340, 740])

    def run_video_trim_tool(self):
        dialog = VideoTrimDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            input_dir = dialog.input_edit.text().strip()
            out_dir = dialog.out_edit.text().strip()
            duration = dialog.duration_spin.value()

            if not input_dir or not out_dir:
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đầy đủ thư mục Input và Output!")
                return

            self.process_btn.setEnabled(False)
            self.select_files_btn.setEnabled(False)
            self.btn_fix_audio.setEnabled(False)
            self.btn_trim_video.setEnabled(False)
            
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            self.trim_worker = VideoTrimWorker(input_dir, out_dir, duration)
            self.trim_worker.progress.connect(self.on_processing_progress)
            self.trim_worker.finished.connect(self.on_video_trim_finished)
            self.trim_worker.error.connect(self.on_processing_error)
            self.trim_worker.start()

    def on_video_trim_finished(self, count):
        self.reset_ui_state()
        self.btn_fix_audio.setEnabled(True)
        self.btn_trim_video.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText(f"Hoàn tất cắt {count} video!")
        self.status_label.setStyleSheet("color: #10B981;")
        QMessageBox.information(self, "Thành công", f"Đã cắt thành công {count} video!")

    def run_audio_fix_tool(self):
        dialog = AudioFixDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            orig_dir = dialog.orig_edit.text().strip()
            cleaned_dir = dialog.clean_edit.text().strip()
            out_dir = dialog.out_edit.text().strip()

            if not orig_dir or not cleaned_dir or not out_dir:
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đầy đủ 3 thư mục!")
                return

            self.process_btn.setEnabled(False)
            self.select_files_btn.setEnabled(False)
            self.btn_fix_audio.setEnabled(False)
            
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.show()

            self.audio_worker = AudioFixWorker(orig_dir, cleaned_dir, out_dir)
            self.audio_worker.progress.connect(self.on_processing_progress)
            self.audio_worker.finished.connect(self.on_audio_fix_finished)
            self.audio_worker.error.connect(self.on_processing_error)
            self.audio_worker.start()

    def on_audio_fix_finished(self, count):
        self.reset_ui_state()
        self.btn_fix_audio.setEnabled(True)
        self.progress_bar.hide()
        self.status_label.setText(f"Hoàn tất ghép tiếng chuẩn cho {count} video!")
        self.status_label.setStyleSheet("color: #10B981;")
        QMessageBox.information(self, "Thành công", f"Đã ghép tiếng nguyên bản AAC chuẩn xác 100% cho {count} video theo đúng tên file!")

    def on_mode_changed(self, checked):
        if self.radio_gemini.isChecked():
            self.custom_pos_widget.hide()
            self.process_btn.setText("⚡ BẮT ĐẦU XÓA WATERMARK (GEMINI)")
        elif self.radio_lama.isChecked():
            self.custom_pos_widget.show()
            self.process_btn.setText("🚀 BẮT ĐẦU XÓA WATERMARK (AI LAMA)")
        else:
            self.custom_pos_widget.show()
            self.process_btn.setText("🚀 BẮT ĐẦU XÓA WATERMARK (OPENCV)")

    def on_preset_changed(self, index):
        preset_name = self.preset_combo.currentText()
        coords = POSITION_PRESETS.get(preset_name)
        if coords:
            x, y, w, h = coords
            self.spin_x.setValue(x)
            self.spin_y.setValue(y)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)

    def on_interactive_roi_selected(self, x_pct, y_pct, w_pct, h_pct):
        if not self.radio_lama.isChecked() and not self.radio_opencv.isChecked():
            self.radio_lama.setChecked(True)

        self.spin_x.setValue(x_pct)
        self.spin_y.setValue(y_pct)
        self.spin_w.setValue(w_pct)
        self.spin_h.setValue(h_pct)
        
        idx = self.preset_combo.findText("Tùy chỉnh Tọa độ %")
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
            
        self.status_label.setText(f"Đã quét chọn vùng AI LaMa xóa: X={x_pct:.1f}%, Y={y_pct:.1f}%, W={w_pct:.1f}%, H={h_pct:.1f}%")
        self.status_label.setStyleSheet("color: #10B981;")

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn File Ảnh hoặc Video",
            "",
            "Media Files (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.webm *.mov *.avi *.mkv);;All Files (*)"
        )
        if files:
            self.load_inputs(files)

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Lưu Output")
        if directory:
            self.output_dir = directory
            self.output_label.setText(f"Output: {directory}")

    def open_output_dir(self):
        target_dir = self.output_dir
        if not target_dir and self.input_paths:
            target_dir = os.path.dirname(self.input_paths[0])
            
        if target_dir and os.path.exists(target_dir):
            if os.name == 'nt':
                os.startfile(target_dir)
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', target_dir])
        else:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có thư mục đầu ra hoặc chưa chọn file!")

    def load_inputs(self, paths):
        valid_files = []
        for p in paths:
            if os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext in SUPPORTED_EXTS:
                    valid_files.append(p)
            elif os.path.isdir(p):
                for root, _, filenames in os.walk(p):
                    for f in filenames:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in SUPPORTED_EXTS:
                            valid_files.append(os.path.join(root, f))
                            
        self.input_paths = valid_files
        
        if not self.input_paths:
            self.drop_area.set_current_pixmap(QPixmap())
            self.process_btn.setEnabled(False)
            self.status_label.setText("Chưa chọn file nào.")
            return

        # Default output is a sibling folder named exactly "Template".
        # Example: ...\Tam Quoc\video.mp4 -> ...\Template\video.mp4.
        source_dir = os.path.dirname(os.path.abspath(self.input_paths[0]))
        source_parent = os.path.dirname(source_dir)
        self.output_dir = os.path.join(source_parent, "Template")
        self.output_label.setText(f"Output: {self.output_dir}")

        first_path = self.input_paths[0]
        ext = os.path.splitext(first_path)[1].lower()

        if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
            pixmap = QPixmap(first_path)
            self.drop_area.set_current_pixmap(pixmap)
            self.status_label.setText(f"Đã nạp {len(self.input_paths)} file. Preview Ảnh: {os.path.basename(first_path)}")
        elif ext in ['.mp4', '.webm', '.mov', '.avi', '.mkv']:
            pixmap = extract_video_first_frame(first_path)
            if pixmap:
                self.drop_area.set_current_pixmap(pixmap)
                self.status_label.setText(f"Đã nạp {len(self.input_paths)} file Video.")
            else:
                self.drop_area.set_current_pixmap(QPixmap())
                self.status_label.setText(f"Đã nạp {len(self.input_paths)} file Video.")

        self.process_btn.setEnabled(True)
        self.auto_detect_btn.setEnabled(True)
        self.status_label.setStyleSheet("color: #F8FAFC;")

    def auto_detect_logo(self):
        """Detect a small, screen-fixed watermark from sampled frames."""
        if not self.input_paths:
            return
        path = self.input_paths[0]
        ext = os.path.splitext(path)[1].lower()
        frames = []
        try:
            if ext in ['.mp4', '.webm', '.mov', '.avi', '.mkv']:
                cap = cv2.VideoCapture(path)
                count = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
                for pos in np.linspace(0, count - 1, min(12, count), dtype=int):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        frames.append(frame)
                cap.release()
            else:
                frame = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    frames.append(frame)

            roi = self._detect_fixed_mark(frames)
            if roi is None:
                QMessageBox.information(self, "Chưa tìm thấy", "Không tìm thấy logo đủ tin cậy. Hãy quét chọn thủ công.")
                return

            x, y, rw, rh = roi
            h, w = frames[0].shape[:2]
            self.on_interactive_roi_selected(x * 100 / w, y * 100 / h, rw * 100 / w, rh * 100 / h)
            pix = self.drop_area.pixmap_item.pixmap()
            if not pix.isNull():
                sx, sy = pix.width() / w, pix.height() / h
                self.drop_area.roi_rect_item.setRect(QRectF(x * sx, y * sy, rw * sx, rh * sy))
                self.drop_area.roi_rect_item.show()
            self.status_label.setText(f"Đã tự tìm logo: X={x}, Y={y}, W={rw}, H={rh}. Hãy kiểm tra khung đỏ.")
        except Exception as exc:
            QMessageBox.warning(self, "Lỗi nhận diện", str(exc))

    @staticmethod
    def _detect_fixed_mark(frames):
        if not frames:
            return None
        h, w = frames[0].shape[:2]
        scale = min(1.0, 720.0 / w)
        sw, sh = int(w * scale), int(h * scale)
        votes = np.zeros((sh, sw), np.float32)
        contrast_sum = np.zeros((sh, sw), np.float32)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))

        for frame in frames:
            small = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            local_bg = cv2.morphologyEx(gray, cv2.MORPH_OPEN, kernel)
            contrast = cv2.subtract(gray, local_bg)
            contrast_sum += contrast.astype(np.float32)
            votes += (contrast > 22).astype(np.float32)

        stable = votes / len(frames)
        avg_contrast = contrast_sum / len(frames)
        mask = ((stable >= (0.65 if len(frames) > 1 else 1.0)) & (avg_contrast > 24)).astype(np.uint8) * 255

        # Watermarks normally occupy a corner; discard the central safe area.
        yy, xx = np.indices((sh, sw))
        outer_x = (xx < sw * .38) | (xx > sw * .62)
        outer_y = (yy < sh * .32) | (yy > sh * .68)
        corner_mask = (outer_x & outer_y).astype(np.uint8)
        mask *= corner_mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)

        # Gemini-generated media uses a consistent translucent sparkle anchor.
        # Check that anchor first; use a padded proportional ROI so the faint
        # arms of the mark are included even when their contrast is low.
        gy1, gy2 = int(sh * .82), int(sh * .97)
        gx1, gx2 = int(sw * .72), int(sw * .96)
        anchor = avg_contrast[gy1:gy2, gx1:gx2]
        if anchor.size and float(np.percentile(anchor, 96)) > 18:
            return (
                int(w * .775), int(h * .868),
                int(w * .130), int(h * .085),
            )

        n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        best = None
        best_score = 0.0
        for i in range(1, n):
            x, y, rw, rh, area = stats[i]
            if area < 35 or area > sw * sh * .035 or rw < 6 or rh < 6:
                continue
            if rw > sw * .28 or rh > sh * .22:
                continue
            patch_stability = float(stable[y:y+rh, x:x+rw].mean())
            patch_contrast = float(avg_contrast[y:y+rh, x:x+rw].mean())
            cx, cy = x + rw / 2, y + rh / 2
            dx = abs(cx - sw/2) / (sw/2)
            dy = abs(cy - sh/2) / (sh/2)
            # Strongly prefer true corner overlays and coherent marks over tiny
            # stationary highlights in the scene.
            edge_bonus = (1.0 + dx + dy) ** 3
            if cx > sw * .62 and cy > sh * .65:
                location_prior = 15.0  # Gemini-style default placement
            elif cy > sh * .65:
                location_prior = 3.0
            else:
                location_prior = 1.0
            score = patch_stability * patch_contrast * edge_bonus * location_prior * np.sqrt(float(area))
            if score > best_score:
                best_score, best = score, (x, y, rw, rh)

        if best is None:
            return None
        x, y, rw, rh = best
        pad = max(5, int(max(rw, rh) * .18))
        x, y = max(0, x-pad), max(0, y-pad)
        rw, rh = min(sw-x, rw+2*pad), min(sh-y, rh+2*pad)
        inv = 1.0 / scale
        return tuple(int(round(v * inv)) for v in (x, y, rw, rh))

    def process_files(self):
        if not self.input_paths:
            return

        self.process_btn.setEnabled(False)
        self.select_files_btn.setEnabled(False)
        self.select_out_btn.setEnabled(False)
        self.drop_area.setEnabled(False)
        self.custom_pos_widget.setEnabled(False)
        
        self.progress_bar.setRange(0, len(self.input_paths))
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        
        self.status_label.setText("Đang xử lý...")
        self.status_label.setStyleSheet("color: #38BDF8;")

        mode = 'opencv'

        roi_params = (
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_w.value(),
            self.spin_h.value()
        )

        self.worker = WatermarkWorker(self.input_paths, self.output_dir, mode=mode, roi_params=roi_params)
        self.worker.progress.connect(self.on_processing_progress)
        self.worker.error.connect(self.on_processing_error)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()

    def on_processing_progress(self, current, total, filename_status):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Đang xử lý ({current}/{total}): {filename_status}")

    def on_processing_finished(self, succeeded, failed):
        self.reset_ui_state()
        self.status_label.setText(f"Hoàn tất: {succeeded} thành công · {failed} lỗi")
        self.status_label.setStyleSheet("color: #10B981;")
        self.progress_bar.setValue(succeeded + failed)

        reply = QMessageBox.information(
            self, 
            "Hoàn tất Xử lý", 
            f"Thành công: {succeeded}\nLỗi: {failed}\n\nBạn có muốn mở thư mục kết quả không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.open_output_dir()

    def on_processing_error(self, error_msg):
        print(f"Worker Error: {error_msg}")
        self.status_label.setStyleSheet("color: #EF4444;")
        self.status_label.setText(f"Lỗi: {error_msg[:70]}...")

    def reset_ui_state(self):
        self.process_btn.setEnabled(True)
        self.select_files_btn.setEnabled(True)
        self.select_out_btn.setEnabled(True)
        self.auto_detect_btn.setEnabled(bool(self.input_paths))
        self.drop_area.setEnabled(True)
        self.custom_pos_widget.setEnabled(True)
        self.btn_fix_audio.setEnabled(True)
        self.btn_trim_video.setEnabled(True)

def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
