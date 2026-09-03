import os
import subprocess
import sys

import cv2
import numpy as np
import qdarktheme
from PyQt6.QtCore import QPointF, QRectF, QSizeF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from worker import IMAGE_EXTS, MEDIA_EXTS, VIDEO_EXTS, WatermarkWorker

SUPPORTED_EXTS = sorted(MEDIA_EXTS)

POSITION_PRESETS = {
    "Góc Dưới - Phải (Bottom-Right)": (85.0, 85.0, 12.0, 12.0),
    "Góc Dưới - Trái (Bottom-Left)": (3.0, 85.0, 12.0, 12.0),
    "Góc Trên - Phải (Top-Right)": (85.0, 3.0, 12.0, 12.0),
    "Góc Trên - Trái (Top-Left)": (3.0, 3.0, 12.0, 12.0),
    "Thanh viền dưới (Bottom Bar)": (0.0, 92.0, 100.0, 8.0),
    "Tùy chỉnh Tọa độ %": None,
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


def frame_to_pixmap(frame):
    """Convert an OpenCV BGR frame to an owned Qt pixmap."""

    if frame is None:
        return QPixmap()
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    height, width, channels = frame_rgb.shape
    image = QImage(
        frame_rgb.data,
        width,
        height,
        channels * width,
        QImage.Format.Format_RGB888,
    )
    return QPixmap.fromImage(image.copy())


def read_video_first_frame(video_path):
    """Read one frame, copying Unicode paths to a temporary ASCII path."""

    temp_dir = None
    try:
        target_path = video_path
        if any(ord(c) > 127 for c in video_path):
            import shutil
            import tempfile

            temp_dir = tempfile.mkdtemp()
            ext = os.path.splitext(video_path)[1] or ".mp4"
            target_path = os.path.join(temp_dir, f"preview_temp{ext}")
            shutil.copy2(video_path, target_path)

        cap = cv2.VideoCapture(target_path)
        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        cap.release()
        return frame if ret else None
    except Exception as e:
        print("Video preview extraction failed:", e)
        return None
    finally:
        if temp_dir:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)


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
        self.current_mode = "select"

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
        if mode == "pan":
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def mousePressEvent(self, event):
        if self.current_mode == "select" and event.button() == Qt.MouseButton.LeftButton:
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GWR Fast Watermark Remover")
        self.setMinimumSize(1080, 780)
        self.input_paths = []
        self.output_dir = None
        self.source_root = None
        self.preview_frame = None
        self.original_preview_pixmap = QPixmap()
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
        badge_sub.setStyleSheet(
            "background: #1E1B4B; color: #A7F3D0; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 11px; border: 1px solid #059669;"
        )

        header_bar.addWidget(brand_label)
        header_bar.addWidget(badge_sub)
        header_bar.addStretch()

        self.open_out_btn = QPushButton("📂 Thư Mục Kết Quả")
        self.open_out_btn.setObjectName("btn_accent_emerald")
        self.open_out_btn.clicked.connect(self.open_output_dir)

        header_bar.addWidget(self.open_out_btn)
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

        # Group 1: Position & Coordinates
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

        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            spin.valueChanged.connect(self._on_roi_value_changed)

        left_layout.addWidget(self.custom_pos_widget)

        # Group 2: Input & Output Location Info
        files_box = QGroupBox("Thông tin Đầu vào / Đầu ra")
        files_layout = QVBoxLayout(files_box)

        self.select_files_btn = QPushButton("📁 Chọn File / Thư mục")
        self.select_files_btn.clicked.connect(self.select_files)
        files_layout.addWidget(self.select_files_btn)

        self.auto_detect_btn = QPushButton("🎯 Tự động tìm Logo")
        self.auto_detect_btn.clicked.connect(self.auto_detect_logo)
        self.auto_detect_btn.setEnabled(False)
        files_layout.addWidget(self.auto_detect_btn)

        self.preview_btn = QPushButton("👁️ Xem trước kết quả")
        self.preview_btn.setCheckable(True)
        self.preview_btn.clicked.connect(self.toggle_preview)
        self.preview_btn.setEnabled(False)
        files_layout.addWidget(self.preview_btn)

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

        self.btn_tool_select.clicked.connect(lambda: self.drop_area.set_mode("select"))
        self.btn_tool_pan.clicked.connect(lambda: self.drop_area.set_mode("pan"))

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
        action_layout = QHBoxLayout()
        self.process_btn = QPushButton("🚀 BẮT ĐẦU XÓA WATERMARK HÀNG LOẠT")
        self.process_btn.setObjectName("btn_primary")
        self.process_btn.setMinimumHeight(48)
        self.process_btn.clicked.connect(self.process_files)
        self.process_btn.setEnabled(False)
        action_layout.addWidget(self.process_btn, stretch=1)

        self.cancel_btn = QPushButton("⏹ Dừng")
        self.cancel_btn.setMinimumHeight(48)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.hide()
        action_layout.addWidget(self.cancel_btn)
        right_layout.addLayout(action_layout)

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

    def on_preset_changed(self, index):
        preset_name = self.preset_combo.currentText()
        coords = POSITION_PRESETS.get(preset_name)
        if coords:
            x, y, w, h = coords
            self.spin_x.setValue(x)
            self.spin_y.setValue(y)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)

    def _on_roi_value_changed(self, _value):
        if self.preview_btn.isChecked() and self.preview_frame is not None:
            self.toggle_preview(True)

    def on_interactive_roi_selected(self, x_pct, y_pct, w_pct, h_pct):
        self.spin_x.setValue(x_pct)
        self.spin_y.setValue(y_pct)
        self.spin_w.setValue(w_pct)
        self.spin_h.setValue(h_pct)

        idx = self.preset_combo.findText("Tùy chỉnh Tọa độ %")
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

        self.status_label.setText(f"Đã chọn ROI: X={x_pct:.1f}%, Y={y_pct:.1f}%, W={w_pct:.1f}%, H={h_pct:.1f}%")
        self.status_label.setStyleSheet("color: #10B981;")
        if self.preview_btn.isChecked():
            self.preview_btn.setChecked(False)
            self.toggle_preview(False)

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn File Ảnh hoặc Video",
            "",
            "Media Files (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.mp4 *.webm *.mov *.avi *.mkv);;All Files (*)",
        )
        if files:
            self.load_inputs(files)

    def select_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Chọn Thư Mục Lưu Output")
        if directory:
            self.output_dir = directory
            self.output_label.setText(f"Output: {directory}")

    def toggle_preview(self, checked):
        """Show a local before/after preview without writing any file."""

        self.preview_btn.setChecked(bool(checked))
        if self.preview_frame is None:
            self.preview_btn.setChecked(False)
            return
        if checked:
            roi_params = (
                self.spin_x.value(),
                self.spin_y.value(),
                self.spin_w.value(),
                self.spin_h.value(),
            )
            roi = WatermarkWorker._roi(self.preview_frame.shape, roi_params)
            result = WatermarkWorker.smart_remove(self.preview_frame.copy(), *roi)
            self.drop_area.set_current_pixmap(frame_to_pixmap(result))
            self._show_roi_overlay(roi, self.preview_frame.shape)
            self.preview_btn.setText("↩️ Xem ảnh gốc")
            self.status_label.setText("Đang xem trước kết quả · chưa ghi file")
            self.status_label.setStyleSheet("color: #38BDF8;")
        else:
            self.drop_area.set_current_pixmap(self.original_preview_pixmap)
            self._show_roi_overlay(
                WatermarkWorker._roi(self.preview_frame.shape, self._current_roi_params()),
                self.preview_frame.shape,
            )
            self.preview_btn.setText("👁️ Xem trước kết quả")
            self.status_label.setText("Đã quay lại ảnh gốc · kiểm tra ROI rồi chạy hàng loạt")
            self.status_label.setStyleSheet("color: #F8FAFC;")

    def _current_roi_params(self):
        return (
            self.spin_x.value(),
            self.spin_y.value(),
            self.spin_w.value(),
            self.spin_h.value(),
        )

    def _show_roi_overlay(self, roi, frame_shape):
        if self.drop_area.pixmap_item.pixmap().isNull():
            return
        x, y, roi_width, roi_height = roi
        height, width = frame_shape[:2]
        pixmap = self.drop_area.pixmap_item.pixmap()
        scale_x, scale_y = pixmap.width() / width, pixmap.height() / height
        self.drop_area.roi_rect_item.setRect(
            QRectF(x * scale_x, y * scale_y, roi_width * scale_x, roi_height * scale_y)
        )
        self.drop_area.roi_rect_item.show()

    def open_output_dir(self):
        target_dir = self.output_dir
        if not target_dir and self.input_paths:
            source_dir = os.path.dirname(os.path.abspath(self.input_paths[0]))
            target_dir = os.path.join(os.path.dirname(source_dir), "Template")

        if target_dir and os.path.exists(target_dir):
            if os.name == "nt":
                os.startfile(target_dir)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target_dir])
        else:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có thư mục đầu ra hoặc chưa chọn file!")

    def load_inputs(self, paths):
        valid_files = []
        seen = set()
        selected_dirs = []
        for raw_path in paths:
            path = os.path.abspath(raw_path)
            if os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in SUPPORTED_EXTS:
                    normalized = os.path.normcase(path)
                    if normalized not in seen:
                        seen.add(normalized)
                        valid_files.append(path)
            elif os.path.isdir(path):
                selected_dirs.append(path)
                for root, dirnames, filenames in os.walk(path):
                    # A previous run writes to Template beside the source
                    # folder. Never feed those generated files back into a
                    # later batch when the parent folder is dropped.
                    dirnames[:] = [name for name in dirnames if name.lower() != "template"]
                    for filename in filenames:
                        if os.path.splitext(filename)[1].lower() not in SUPPORTED_EXTS:
                            continue
                        candidate = os.path.join(root, filename)
                        normalized = os.path.normcase(os.path.abspath(candidate))
                        if normalized not in seen:
                            seen.add(normalized)
                            valid_files.append(candidate)

        self.input_paths = sorted(valid_files, key=lambda value: value.casefold())

        if not self.input_paths:
            self.drop_area.set_current_pixmap(QPixmap())
            self.process_btn.setEnabled(False)
            self.auto_detect_btn.setEnabled(False)
            self.preview_btn.setChecked(False)
            self.preview_btn.setEnabled(False)
            self.preview_frame = None
            self.original_preview_pixmap = QPixmap()
            self.status_label.setText("Chưa chọn file nào.")
            return

        # Default output is a sibling folder named exactly "Template".
        # Example: ...\Tam Quoc\video.mp4 -> ...\Template\video.mp4.
        source_dir = (
            os.path.abspath(selected_dirs[0])
            if len(selected_dirs) == 1
            else os.path.dirname(os.path.abspath(self.input_paths[0]))
        )
        source_parent = os.path.dirname(source_dir)
        self.output_dir = os.path.join(source_parent, "Template")
        self.output_label.setText(f"Output: {self.output_dir}")

        # Preserve nested folders when a whole directory is selected. For a
        # list of individual files, use their common parent where possible.
        if len(selected_dirs) == 1:
            self.source_root = os.path.abspath(selected_dirs[0])
        else:
            try:
                self.source_root = os.path.commonpath([os.path.dirname(path) for path in self.input_paths])
            except ValueError:
                self.source_root = None

        first_path = self.input_paths[0]
        ext = os.path.splitext(first_path)[1].lower()

        self.preview_frame = None
        if ext in IMAGE_EXTS:
            self.preview_frame = cv2.imdecode(np.fromfile(first_path, dtype=np.uint8), cv2.IMREAD_COLOR)
            pixmap = frame_to_pixmap(self.preview_frame)
            self.original_preview_pixmap = pixmap
            self.drop_area.set_current_pixmap(pixmap)
            self.status_label.setText(
                f"Đã nạp {len(self.input_paths)} file. Preview Ảnh: {os.path.basename(first_path)}"
            )
        elif ext in VIDEO_EXTS:
            self.preview_frame = read_video_first_frame(first_path)
            pixmap = frame_to_pixmap(self.preview_frame)
            self.original_preview_pixmap = pixmap
            if not pixmap.isNull():
                self.drop_area.set_current_pixmap(pixmap)
                self.status_label.setText(f"Đã nạp {len(self.input_paths)} file Video.")
            else:
                self.drop_area.set_current_pixmap(QPixmap())
                self.status_label.setText(f"Đã nạp {len(self.input_paths)} file Video.")

        self.process_btn.setEnabled(True)
        self.auto_detect_btn.setEnabled(True)
        self.preview_btn.setChecked(False)
        self.preview_btn.setEnabled(self.preview_frame is not None)
        self.preview_btn.setText("👁️ Xem trước kết quả")
        self.status_label.setStyleSheet("color: #F8FAFC;")

    def auto_detect_logo(self):
        """Detect a small, screen-fixed watermark from sampled frames."""
        if not self.input_paths:
            return
        path = self.input_paths[0]
        ext = os.path.splitext(path)[1].lower()
        frames = []
        temp_dir = None
        try:
            if ext in VIDEO_EXTS:
                target_path = path
                if any(ord(char) > 127 for char in path):
                    import shutil
                    import tempfile

                    temp_dir = tempfile.mkdtemp(prefix="gwr_detect_")
                    target_path = os.path.join(temp_dir, "input" + (os.path.splitext(path)[1] or ".mp4"))
                    shutil.copy2(path, target_path)
                cap = cv2.VideoCapture(target_path)
                if not cap.isOpened():
                    raise ValueError("Không mở được video để nhận diện.")
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
                QMessageBox.information(
                    self, "Chưa tìm thấy", "Không tìm thấy logo đủ tin cậy. Hãy quét chọn thủ công."
                )
                return

            x, y, rw, rh = roi
            h, w = frames[0].shape[:2]
            self.on_interactive_roi_selected(x * 100 / w, y * 100 / h, rw * 100 / w, rh * 100 / h)
            self._show_roi_overlay((x, y, rw, rh), frames[0].shape)
            self.status_label.setText(f"Đã tự tìm logo: X={x}, Y={y}, W={rw}, H={rh}. Hãy kiểm tra khung đỏ.")
        except Exception as exc:
            QMessageBox.warning(self, "Lỗi nhận diện", str(exc))
        finally:
            if temp_dir:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

    @staticmethod
    def _detect_fixed_mark(frames):
        if not frames:
            return None
        h, w = frames[0].shape[:2]
        scale = min(1.0, 720.0 / w)
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
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
        outer_x = (xx < sw * 0.38) | (xx > sw * 0.62)
        outer_y = (yy < sh * 0.32) | (yy > sh * 0.68)
        corner_mask = (outer_x & outer_y).astype(np.uint8)
        mask *= corner_mask
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)

        # Gemini-generated media uses a consistent translucent sparkle anchor.
        # Check that anchor first; use a padded proportional ROI so the faint
        # arms of the mark are included even when their contrast is low.
        gy1, gy2 = int(sh * 0.82), int(sh * 0.97)
        gx1, gx2 = int(sw * 0.72), int(sw * 0.96)
        anchor = avg_contrast[gy1:gy2, gx1:gx2]
        if anchor.size and float(np.percentile(anchor, 96)) > 18:
            return (
                int(w * 0.775),
                int(h * 0.868),
                int(w * 0.130),
                int(h * 0.085),
            )

        n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        best = None
        best_score = 0.0
        for i in range(1, n):
            x, y, rw, rh, area = stats[i]
            if area < 35 or area > sw * sh * 0.035 or rw < 6 or rh < 6:
                continue
            if rw > sw * 0.28 or rh > sh * 0.22:
                continue
            patch_stability = float(stable[y : y + rh, x : x + rw].mean())
            patch_contrast = float(avg_contrast[y : y + rh, x : x + rw].mean())
            cx, cy = x + rw / 2, y + rh / 2
            dx = abs(cx - sw / 2) / (sw / 2)
            dy = abs(cy - sh / 2) / (sh / 2)
            # Strongly prefer true corner overlays and coherent marks over tiny
            # stationary highlights in the scene.
            edge_bonus = (1.0 + dx + dy) ** 3
            if cx > sw * 0.62 and cy > sh * 0.65:
                location_prior = 15.0  # Gemini-style default placement
            elif cy > sh * 0.65:
                location_prior = 3.0
            else:
                location_prior = 1.0
            score = patch_stability * patch_contrast * edge_bonus * location_prior * np.sqrt(float(area))
            if score > best_score:
                best_score, best = score, (x, y, rw, rh)

        if best is None:
            return None
        x, y, rw, rh = best
        pad = max(5, int(max(rw, rh) * 0.18))
        x, y = max(0, x - pad), max(0, y - pad)
        rw, rh = min(sw - x, rw + 2 * pad), min(sh - y, rh + 2 * pad)
        inv = 1.0 / scale
        return tuple(int(round(v * inv)) for v in (x, y, rw, rh))

    def process_files(self):
        if not self.input_paths:
            return

        self.process_btn.setEnabled(False)
        self.select_files_btn.setEnabled(False)
        self.select_out_btn.setEnabled(False)
        self.auto_detect_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        self.drop_area.setEnabled(False)
        self.custom_pos_widget.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.cancel_btn.show()

        self.progress_bar.setRange(0, len(self.input_paths))
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        self.status_label.setText("Đang xử lý...")
        self.status_label.setStyleSheet("color: #38BDF8;")

        self.worker = WatermarkWorker(
            self.input_paths,
            self.output_dir,
            mode="smart",
            roi_params=self._current_roi_params(),
            source_root=self.source_root,
        )
        self.worker.progress.connect(self.on_processing_progress)
        self.worker.error.connect(self.on_processing_error)
        self.worker.finished.connect(self.on_processing_finished)
        self.worker.start()

    def cancel_processing(self):
        if self.worker and self.worker.isRunning():
            self.cancel_btn.setEnabled(False)
            self.status_label.setText("Đang dừng an toàn…")
            self.status_label.setStyleSheet("color: #F59E0B;")
            self.worker.cancel()

    def on_processing_progress(self, current, total, filename_status):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Đang xử lý ({current}/{total}): {filename_status}")

    def on_processing_finished(self, succeeded, failed):
        was_cancelled = bool(self.worker and self.worker.was_cancelled)
        self.reset_ui_state()
        if was_cancelled:
            self.status_label.setText(f"Đã dừng: {succeeded} thành công · {failed} lỗi")
            self.status_label.setStyleSheet("color: #F59E0B;")
        else:
            self.status_label.setText(f"Hoàn tất: {succeeded} thành công · {failed} lỗi")
            self.status_label.setStyleSheet("color: #10B981;")
        self.progress_bar.setValue(succeeded + failed)

        if was_cancelled:
            QMessageBox.information(
                self,
                "Đã dừng",
                f"Thành công: {succeeded}\nLỗi: {failed}\n\nMột số file chưa chạy do bạn đã dừng tác vụ.",
            )
        else:
            reply = QMessageBox.information(
                self,
                "Hoàn tất Xử lý",
                f"Thành công: {succeeded}\nLỗi: {failed}\n\nBạn có muốn mở thư mục kết quả không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.open_output_dir()

    def on_processing_error(self, error_msg):
        print(f"Worker Error: {error_msg}")
        self.status_label.setStyleSheet("color: #EF4444;")
        self.status_label.setText(f"Lỗi: {error_msg[:70]}...")

    def reset_ui_state(self):
        self.process_btn.setEnabled(bool(self.input_paths))
        self.select_files_btn.setEnabled(True)
        self.select_out_btn.setEnabled(True)
        self.auto_detect_btn.setEnabled(bool(self.input_paths))
        self.preview_btn.setEnabled(self.preview_frame is not None)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.hide()
        self.drop_area.setEnabled(True)
        self.custom_pos_widget.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
