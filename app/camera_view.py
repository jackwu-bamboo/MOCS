"""明场显微成像实时显示（nncam 相机 SDK）。

流程与 SDK 示例 python/samples/qt5.py 一致：枚举 → 打开 → 拉流回调。
回调只发 Qt 信号（SDK 回调在内部线程），在界面线程里 PullImageV4 取图并显示。
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.vendor import nncam

NO_CAMERA = "未检测到相机"


class MicroscopeView(QWidget):
    evt_callback = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hcam = None
        self.cur = None
        self.buf = None
        self.width = 0
        self.height = 0

        self.btn = QPushButton("打开相机")
        self.btn.clicked.connect(self._on_button)
        self.status = QLabel("相机未打开")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #8fa8a4;")
        bar = QHBoxLayout()
        bar.addWidget(self.btn)
        bar.addWidget(self.status, 1)

        self.image = QLabel("点击“打开相机”开始实时显示")
        self.image.setWordWrap(True)
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(120, 90)
        self.image.setStyleSheet("background:#0e211f; color:#8fa8a4;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addLayout(bar)
        lay.addWidget(self.image, 1)

        self.evt_callback.connect(self._on_event)

    def _on_button(self):
        if self.hcam:
            self.close_camera()
        else:
            self.open_camera()

    def open_camera(self):
        arr = nncam.Nncam.EnumV2()
        if not arr:
            self.status.setText(NO_CAMERA)
            return
        self.cur = arr[0]
        hcam = nncam.Nncam.Open(self.cur.id)
        if not hcam:
            self.status.setText("相机打开失败")
            return
        self.hcam = hcam
        self.hcam.put_Option(nncam.NNCAM_OPTION_BYTEORDER, 0)  # Qt 使用 RGB 字节序
        self.hcam.put_AutoExpoEnable(1)
        self.width, self.height = self.hcam.get_Size()
        self.buf = bytes(nncam.TDIBWIDTHBYTES(self.width * 24) * self.height)
        try:
            self.hcam.StartPullModeWithCallback(self._sdk_callback, self)
        except nncam.HRESULTException:
            self.close_camera()
            self.status.setText("相机启动失败")
            return
        self.btn.setText("关闭相机")
        self.status.setText(f"{self.cur.displayname}  {self.width}×{self.height}")

    def close_camera(self):
        if self.hcam:
            self.hcam.Close()
        self.hcam = None
        self.buf = None
        self.btn.setText("打开相机")
        self.status.setText("相机未打开")
        self.image.clear()
        self.image.setText("点击“打开相机”开始实时显示")

    @staticmethod
    def _sdk_callback(event, self):
        """SDK 内部线程回调：只发信号，取图放到界面线程。"""
        self.evt_callback.emit(event)

    def _on_event(self, event):
        if not self.hcam:
            return
        if event == nncam.NNCAM_EVENT_IMAGE:
            self._pull_image()
        elif event == nncam.NNCAM_EVENT_ERROR:
            self.close_camera()
            self.status.setText("相机错误，已关闭")

    def _pull_image(self):
        try:
            self.hcam.PullImageV4(self.buf, 0, 24, 0, None)
        except nncam.HRESULTException:
            return
        img = QImage(self.buf, self.width, self.height, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(img).scaled(
            self.image.width(), self.image.height(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.image.setPixmap(pix)

    def shutdown(self):
        self.close_camera()
