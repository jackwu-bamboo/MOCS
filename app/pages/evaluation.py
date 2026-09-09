"""损伤评价界面：多模态指标展示、综合评分、趋势分析、实验报告。"""
import os
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                             QPushButton, QVBoxLayout, QWidget)

from app.widgets import Card, CurvePlot, ValueCard


class EvaluationPage(QWidget):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        self.cards = {
            "放电频率": ValueCard("放电频率", "Hz"),
            "Spike 数量": ValueCard("Spike 数量", "个/5s"),
            "信号幅值": ValueCard("信号幅值", "µV"),
            "TEER": ValueCard("TEER", "Ω·cm²"),
            "代谢物": ValueCard("代谢物浓度", "mM"),
            "形态变化": ValueCard("组织形态变化", "%"),
        }
        for card in self.cards.values():
            top.addWidget(card)
        root.addLayout(top)

        mid = QHBoxLayout()
        score_card = Card("综合损伤评分")
        self.score_label = QLabel("0.0")
        self.score_label.setObjectName("BigValue")
        self.score_label.setAlignment(Qt.AlignCenter)
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.grade = QLabel("状态良好")
        self.grade.setAlignment(Qt.AlignCenter)
        score_card.body.addWidget(self.score_label)
        score_card.body.addWidget(self.score_bar)
        score_card.body.addWidget(self.grade)
        mid.addWidget(score_card, 1)

        trend_card = Card("损伤评分时间趋势")
        self.score_plot = CurvePlot("综合损伤评分 (0-100)")
        self.score_plot.add_series(self.sim.history["score"], "#ff8a65", "评分")
        trend_card.body.addWidget(self.score_plot)
        mid.addWidget(trend_card, 2)
        root.addLayout(mid, 1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.b_report = QPushButton("生成实验报告")
        self.b_report.clicked.connect(self.report)
        bottom.addWidget(self.b_report)
        root.addLayout(bottom)

        sim.states_updated.connect(self.refresh)
        self.refresh()

    def refresh(self):
        s = self.sim
        self.cards["放电频率"].set_value(f"{s.spike_rate:.2f}")
        self.cards["Spike 数量"].set_value(f"{s.spike_rate * 5:.0f}")
        self.cards["信号幅值"].set_value(f"{40 + s.spike_rate * 8:.0f}")
        self.cards["TEER"].set_value(f"{s.teer:.0f}")
        self.cards["代谢物"].set_value(f"{s.echem:.3f}")
        self.cards["形态变化"].set_value(f"{s.damage_score * 0.4:.1f}")

        score = s.damage_score
        self.score_label.setText(f"{score:.1f}")
        self.score_bar.setValue(int(score))
        if score < 30:
            grade, color = "状态良好", "#00e676"
        elif score < 60:
            grade, color = "轻度损伤", "#ffb74d"
        else:
            grade, color = "严重损伤", "#ff5252"
        self.grade.setText(grade)
        self.score_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")

    def report(self):
        s = self.sim
        os.makedirs("exports", exist_ok=True)
        path = os.path.join("exports", time.strftime("report_%Y%m%d_%H%M%S.txt"))
        with open(path, "w", encoding="utf-8") as f:
            f.write("多器官芯片培养盒 实验报告\n")
            f.write("=" * 40 + "\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("[环境参数]\n")
            f.write(f"  当前温度: {s.temp_current:.2f} ℃ (目标 {s.temp_target:.1f} ℃)\n")
            f.write(f"  当前氧浓度: {s.o2_current:.2f} % (目标 {s.o2_target:.1f} %)\n\n")
            f.write("[检测指标]\n")
            f.write(f"  放电频率: {s.spike_rate:.2f} Hz\n")
            f.write(f"  TEER: {s.teer:.0f} Ω·cm² (基线 {s.teer_baseline:.0f})\n")
            f.write(f"  代谢物浓度: {s.echem:.3f} mM\n\n")
            f.write(f"[综合损伤评分] {s.damage_score:.1f} / 100\n")
        QMessageBox.information(self, "报告已生成", f"实验报告已保存到:\n{os.path.abspath(path)}")
