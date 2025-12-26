# ============================================================
# ======================= IMPORTS ============================
# ============================================================

import sys
import os
import time
import math
import platform
import cv2
import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QStackedLayout
)

from mmpose.apis import MMPoseInferencer

# ============================================================
# =============== PYINSTALLER RESOURCE HELPER =================
# ============================================================

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS   # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ============================================================
# ======================= ASSETS =============================
# ============================================================

SPLASH_IMAGE = resource_path("front_1080p.png")
INSTRUCTIONS_IMAGE = resource_path("instructions1.png")
BACKGROUND_IMAGE = resource_path("background_kick.png")
FOOTBALL_IMAGE = resource_path("ball.png")

PLAY_BUTTON_IMAGE = resource_path("play1.png")
EXIT_BUTTON_IMAGE = resource_path("exit1.png")



# ============================================================
# ======================= GLOBAL STATE =======================
# ============================================================

FLIP_FRAME = True

SESSION_TIME_SECONDS = 30

BALL_HORIZONTAL_OFFSET = 80
BALL_RADIUS = 35
HIT_RADIUS = BALL_RADIUS
HOLD_TIME = 0.5
MIN_KICK_INTERVAL = 0.3

DIFFICULTY_MAP = {1: 0, 2: 15, 3: 30}

selected_posture = "standing"
selected_difficulty = 1


# ============================================================
# ======================= SOUND ==============================
# ============================================================

def play_beep():
    if platform.system() == "Windows":
        import winsound
        winsound.Beep(1000, 150)
    else:
        print("\a", end="", flush=True)


# ============================================================
# ===================== GLOW STYLES ==========================
# ============================================================

GLOW_SELECTED_STYLE = """
QPushButton {
    background-color: rgba(0, 220, 255, 230);
    color: black;
    font-size: 28px;
    font-weight: bold;
    border-radius: 22px;
    border: 3px solid white;
}
"""

GLOW_UNSELECTED_STYLE = """
QPushButton {
    background-color: rgba(0,0,0,180);
    color: white;
    font-size: 28px;
    font-weight: bold;
    border-radius: 22px;
    border: 2px solid #64748b;
}
QPushButton:hover {
    border: 2px solid #67e8f9;
}
"""


# ============================================================
# ============ FIXED IMAGE BUTTON (NO SIZE BUG) ==============
# ============================================================

class ImageButton(QPushButton):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)

        self.original_pixmap = QPixmap(image_path)
        self.base_pixmap = self.original_pixmap
        self.hover_pixmap = self._brighten(self.original_pixmap, 1.08)
        self.pressed_pixmap = self._darken(self.original_pixmap, 0.9)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("border: none; background: transparent;")

        self._apply_pixmap(self.base_pixmap)

    def _apply_pixmap(self, pix):
        self.setIcon(QIcon(pix))
        self.setIconSize(pix.size())
        self.setFixedSize(pix.size())

    def set_scaled_width(self, width):
        self.base_pixmap = self.original_pixmap.scaledToWidth(
            width, Qt.TransformationMode.SmoothTransformation
        )
        self.hover_pixmap = self._brighten(self.base_pixmap, 1.08)
        self.pressed_pixmap = self._darken(self.base_pixmap, 0.9)
        self._apply_pixmap(self.base_pixmap)

    def enterEvent(self, event):
        self._apply_pixmap(self.hover_pixmap)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_pixmap(self.base_pixmap)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._apply_pixmap(self.pressed_pixmap)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._apply_pixmap(self.hover_pixmap)
        super().mouseReleaseEvent(event)

    def _brighten(self, pix, factor):
        img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                c.setRed(min(255, int(c.red() * factor)))
                c.setGreen(min(255, int(c.green() * factor)))
                c.setBlue(min(255, int(c.blue() * factor)))
                img.setPixelColor(x, y, c)
        return QPixmap.fromImage(img)

    def _darken(self, pix, factor):
        img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                c.setRed(int(c.red() * factor))
                c.setGreen(int(c.green() * factor))
                c.setBlue(int(c.blue() * factor))
                img.setPixelColor(x, y, c)
        return QPixmap.fromImage(img)

# ============================================================
# ======================= SPLASH SCREEN ======================
# ============================================================

class SplashScreen(QWidget):
    def __init__(self, on_play, on_exit):
        super().__init__()

        self.bg_label = QLabel(self)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_pixmap = QPixmap(SPLASH_IMAGE)

        self.play_btn = ImageButton(PLAY_BUTTON_IMAGE, self)
        self.exit_btn = ImageButton(EXIT_BUTTON_IMAGE, self)

        self.play_btn.clicked.connect(on_play)
        self.exit_btn.clicked.connect(on_exit)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if not self.bg_pixmap.isNull():
            bg = self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.bg_label.setPixmap(bg)
            self.bg_label.resize(self.size())

        btn_w = int(self.width() * 0.18)
        self.play_btn.set_scaled_width(btn_w)
        self.exit_btn.set_scaled_width(btn_w)

        spacing = int(btn_w * 0.3)
        total_w = self.play_btn.width() + self.exit_btn.width() + spacing
        x = (self.width() - total_w) // 2
        y = int(self.height() * 0.7)

        self.play_btn.move(x, y)
        self.exit_btn.move(x + self.play_btn.width() + spacing, y)


# ============================================================
# =================== INSTRUCTIONS SCREEN ====================
# ============================================================

class InstructionsScreen(QWidget):
    def __init__(self, on_next, on_back):
        super().__init__()

        self.bg_label = QLabel(self)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_pixmap = QPixmap(INSTRUCTIONS_IMAGE)

        self.footer = QWidget(self)
        self.footer.setStyleSheet("""
            QWidget {
                background-color: rgba(2, 6, 23, 200);
            }
        """)

        self.next_btn = QPushButton("NEXT", self.footer)
        self.back_btn = QPushButton("BACK", self.footer)

        for btn in (self.next_btn, self.back_btn):
            btn.setFixedSize(220, 60)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #020617;
                    color: #e5e7eb;
                    font-size: 20px;
                    font-weight: bold;
                    border-radius: 18px;
                    border: 2px solid #38bdf8;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                }
            """)

        self.next_btn.clicked.connect(on_next)
        self.back_btn.clicked.connect(on_back)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if not self.bg_pixmap.isNull():
            bg = self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            self.bg_label.setPixmap(bg)
            self.bg_label.resize(self.size())

        footer_h = int(self.height() * 0.18)
        self.footer.setGeometry(0, self.height() - footer_h, self.width(), footer_h)

        spacing = 30
        total_w = self.next_btn.width() + self.back_btn.width() + spacing
        x = (self.width() - total_w) // 2
        y = (footer_h - self.next_btn.height()) // 2

        self.back_btn.move(x, y)
        self.next_btn.move(x + self.back_btn.width() + spacing, y)


# ============================================================
# =================== TITLE / BUTTON HELPERS =================
# ============================================================

def create_title(parent, text):
    panel = QWidget(parent)
    panel.setStyleSheet("""
        QWidget {
            background-color: rgba(2,6,23,200);
            border-radius: 16px;
        }
    """)
    label = QLabel(text, panel)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("""
        QLabel {
            font-size: 40px;
            font-weight: bold;
            color: #67e8f9;
        }
    """)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(20, 10, 20, 10)
    layout.addWidget(label)
    return panel


def nav_button(parent, text):
    btn = QPushButton(text, parent)
    btn.setFixedSize(180, 55)
    btn.setStyleSheet("""
        QPushButton {
            background-color: #020617;
            color: #e5e7eb;
            font-size: 18px;
            border-radius: 16px;
            border: 2px solid #38bdf8;
        }
        QPushButton:hover {
            background-color: #1e293b;
        }
    """)
    return btn


def choice_button(parent, text, w=360, h=90):
    btn = QPushButton(text, parent)
    btn.setFixedSize(w, h)
    btn.setStyleSheet(GLOW_UNSELECTED_STYLE)
    return btn

# ============================================================
# ==================== POSTURE SCREEN ========================
# ============================================================

class PostureScreen(QWidget):
    def __init__(self, on_next, on_back):
        super().__init__()

        self.bg = QLabel(self)
        self.bg_pixmap = QPixmap(BACKGROUND_IMAGE)
        self.bg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = create_title(self, "SELECT POSTURE")

        self.standing_btn = choice_button(self, "STANDING")
        self.sitting_btn = choice_button(self, "SITTING")

        self.standing_btn.clicked.connect(lambda: self.select("standing"))
        self.sitting_btn.clicked.connect(lambda: self.select("sitting"))

        self.back_btn = nav_button(self, "BACK")
        self.next_btn = nav_button(self, "NEXT")

        self.back_btn.clicked.connect(on_back)
        self.next_btn.clicked.connect(on_next)

        self.refresh()

    def select(self, posture):
        global selected_posture
        selected_posture = posture
        self.refresh()

    def refresh(self):
        if selected_posture == "standing":
            self.standing_btn.setStyleSheet(GLOW_SELECTED_STYLE)
            self.sitting_btn.setStyleSheet(GLOW_UNSELECTED_STYLE)
        else:
            self.sitting_btn.setStyleSheet(GLOW_SELECTED_STYLE)
            self.standing_btn.setStyleSheet(GLOW_UNSELECTED_STYLE)

    def resizeEvent(self, e):
        self.bg.setPixmap(
            self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.bg.resize(self.size())

        self.title.setGeometry(
            self.width() // 2 - 260, int(self.height() * 0.08), 520, 70
        )

        y = int(self.height() * 0.35)
        self.standing_btn.move(self.width() // 2 - 180, y)
        self.sitting_btn.move(self.width() // 2 - 180, y + 120)

        nav_y = int(self.height() * 0.82)
        self.back_btn.move(self.width() // 2 - 200, nav_y)
        self.next_btn.move(self.width() // 2 + 20, nav_y)


# ============================================================
# =================== DIFFICULTY SCREEN ======================
# ============================================================

class DifficultyScreen(QWidget):
    def __init__(self, on_next, on_back):
        super().__init__()

        self.bg = QLabel(self)
        self.bg_pixmap = QPixmap(BACKGROUND_IMAGE)
        self.bg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = create_title(self, "SELECT DIFFICULTY")

        self.buttons = []
        for lvl in (1, 2, 3):
            btn = choice_button(self, f"LEVEL {lvl}", 300, 80)
            btn.clicked.connect(lambda _, l=lvl: self.select(l))
            self.buttons.append(btn)

        self.back_btn = nav_button(self, "BACK")
        self.next_btn = nav_button(self, "NEXT")

        self.back_btn.clicked.connect(on_back)
        self.next_btn.clicked.connect(on_next)

        self.refresh()

    def select(self, lvl):
        global selected_difficulty
        selected_difficulty = lvl
        self.refresh()

    def refresh(self):
        for i, btn in enumerate(self.buttons, start=1):
            if selected_difficulty == i:
                btn.setStyleSheet(GLOW_SELECTED_STYLE)
            else:
                btn.setStyleSheet(GLOW_UNSELECTED_STYLE)

    def resizeEvent(self, e):
        self.bg.setPixmap(
            self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.bg.resize(self.size())

        self.title.setGeometry(
            self.width() // 2 - 260, int(self.height() * 0.08), 520, 70
        )

        y = int(self.height() * 0.32)
        for i, btn in enumerate(self.buttons):
            btn.move(self.width() // 2 - 150, y + i * 110)

        nav_y = int(self.height() * 0.82)
        self.back_btn.move(self.width() // 2 - 200, nav_y)
        self.next_btn.move(self.width() // 2 + 20, nav_y)


# ============================================================
# ==================== TIME SELECTION ========================
# ============================================================

class TimeSelectScreen(QWidget):
    def __init__(self, on_next, on_back):
        super().__init__()

        self.bg = QLabel(self)
        self.bg_pixmap = QPixmap(BACKGROUND_IMAGE)
        self.bg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title = create_title(self, "SELECT TIME")

        self.time_label = QLabel(self)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("""
            QLabel {
                font-size: 48px;
                font-weight: bold;
                color: #b59f00;
            }
        """)

        self.minus_btn = nav_button(self, "−")
        self.plus_btn = nav_button(self, "+")

        self.minus_btn.setFixedSize(80, 60)
        self.plus_btn.setFixedSize(80, 60)

        self.minus_btn.clicked.connect(self.decrease)
        self.plus_btn.clicked.connect(self.increase)

        self.back_btn = nav_button(self, "BACK")
        self.next_btn = nav_button(self, "START")

        self.back_btn.clicked.connect(on_back)
        self.next_btn.clicked.connect(on_next)

        self.update_label()

    def decrease(self):
        global SESSION_TIME_SECONDS
        SESSION_TIME_SECONDS = max(10, SESSION_TIME_SECONDS - 5)
        self.update_label()

    def increase(self):
        global SESSION_TIME_SECONDS
        SESSION_TIME_SECONDS = min(120, SESSION_TIME_SECONDS + 5)
        self.update_label()

    def update_label(self):
        self.time_label.setText(f"{SESSION_TIME_SECONDS} s")

    def resizeEvent(self, e):
        self.bg.setPixmap(
            self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.bg.resize(self.size())

        self.title.setGeometry(
            self.width() // 2 - 260, int(self.height() * 0.08), 520, 70
        )

        y = int(self.height() * 0.48)

        self.minus_btn.move(self.width() // 2 - 160, y)
        self.time_label.setGeometry(
            self.width() // 2 - 60,
            y,
            120,
            60
        )
        self.plus_btn.move(self.width() // 2 + 100, y)


        nav_y = int(self.height() * 0.82)
        self.back_btn.move(self.width() // 2 - 200, nav_y)
        self.next_btn.move(self.width() // 2 + 20, nav_y)


# ============================================================
# ================= GAME STATE HELPERS =======================
# ============================================================

def reset_game_state():
    return {
        "BALL_SIDES": ["left", "right"],
        "current_side_index": 0,
        "level": 1,
        "total_kicks": 0,
        "kick_times": [],
        "ball_spawn_time": time.time(),
        "last_kick_time": time.time() - 10,
        "in_ball": False,
        "in_ball_since": 0.0,
        "must_leave_ball": False,
        "last_hit_time": 0.0
    }


def unpack_xy(kpt):
    if len(kpt) >= 2:
        return float(kpt[0]), float(kpt[1])
    return 0.0, 0.0


# ============================================================
# ====================== GAME WIDGET =========================
# ============================================================

class GameWidget(QWidget):
    def __init__(self, on_back, on_session_end):
        super().__init__()

        self.on_back = on_back
        self.on_session_end = on_session_end

        # ---------- VIDEO ----------
        self.video_label = QLabel(self)
        self.video_label.setScaledContents(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_label)

        # ---------- HUD ----------
        self.hud = QWidget(self)
        self.hud.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hud_layout = QVBoxLayout(self.hud)
        self.hud_layout.setContentsMargins(20, 20, 20, 20)

        self.time_label = QLabel("TIME: 30s", self.hud)
        self.kick_label = QLabel("KICKS: 0", self.hud)

        for lbl in (self.time_label, self.kick_label):
            lbl.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 22px;
                    font-weight: bold;
                    background-color: rgba(2,6,23,180);
                    padding: 8px 14px;
                    border-radius: 10px;
                }
            """)

        self.hud_layout.addWidget(self.time_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.hud_layout.addSpacing(8)
        self.hud_layout.addWidget(self.kick_label, alignment=Qt.AlignmentFlag.AlignLeft)
        self.hud_layout.addStretch()

        # ---------- BACK BUTTON ----------
        self.back_btn = QPushButton("BACK", self)
        self.back_btn.setFixedSize(140, 44)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(2,6,23,200);
                color: #e5e7eb;
                font-size: 16px;
                border-radius: 14px;
                border: 2px solid #38bdf8;
            }
            QPushButton:hover {
                background-color: #1e293b;
            }
        """)
        self.back_btn.clicked.connect(self.handle_back)

        # ---------- CAMERA & POSE ----------
        self.cap = cv2.VideoCapture(0)
        self.inferencer = MMPoseInferencer("human")
        self.ball_png = cv2.imread(FOOTBALL_IMAGE, cv2.IMREAD_UNCHANGED)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_tick)

    # ========================================================
    # ===================== CONTROL ==========================
    # ========================================================

    def start(self):
        self.game_state = reset_game_state()
        self.start_time = time.time()
        self.difficulty_step = DIFFICULTY_MAP[selected_difficulty]
        self.sitting_mode = (selected_posture == "sitting")
        self.timer.start(16)

    def stop(self):
        self.timer.stop()

    def handle_back(self):
        self.stop()
        self.on_back()

    # ========================================================
    # ===================== GAME LOOP ========================
    # ========================================================

    def game_tick(self):
        ret, frame = self.cap.read()
        if not ret:
            return

        if FLIP_FRAME:
            frame = cv2.flip(frame, 1)

        elapsed = time.time() - self.start_time
        time_left = max(0, int(SESSION_TIME_SECONDS - elapsed))

        if time_left <= 0:
            self.stop()
            self.on_session_end(self.game_state)
            return

        self.time_label.setText(f"TIME: {time_left}s")
        self.kick_label.setText(f"KICKS: {self.game_state['total_kicks']}")

        result = next(self.inferencer(frame, show=False))
        preds = result.get("predictions", [])

        if preds and preds[0] and len(preds[0][0]["keypoints"]) >= 15:
            keypoints = preds[0][0]["keypoints"]

            lx, ly = unpack_xy(keypoints[11])
            rx, ry = unpack_xy(keypoints[12])
            hip_x = (lx + rx) / 2
            hip_y = (ly + ry) / 2

            k0x, k0y = unpack_xy(keypoints[13])
            k1x, k1y = unpack_xy(keypoints[14])

            # Identify left/right knee by X position
            if k0x <= k1x:
                left_knee = (int(k0x), int(k0y))
                right_knee = (int(k1x), int(k1y))
            else:
                left_knee = (int(k1x), int(k1y))
                right_knee = (int(k0x), int(k0y))

            # -------- DRAW KNEE TRACKERS --------
            cv2.circle(frame, left_knee, 14, (0, 255, 0), -1)   # GREEN
            cv2.circle(frame, right_knee, 14, (0, 0, 255), -1) # RED

            side = self.game_state["BALL_SIDES"][self.game_state["current_side_index"]]
            knee_x, knee_y = left_knee if side == "left" else right_knee

            offset = BALL_HORIZONTAL_OFFSET * (0.6 if self.sitting_mode else 1.0)
            ball_x = hip_x - offset if side == "left" else hip_x + offset
            ball_y = hip_y - self.difficulty_step


            now = time.time()
            dist = math.dist((knee_x, knee_y), (ball_x, ball_y))
            inside = dist <= HIT_RADIUS

            if inside:
                if not self.game_state["in_ball"]:
                    self.game_state["in_ball"] = True
                    self.game_state["in_ball_since"] = now
                else:
                    if (
                        not self.game_state["must_leave_ball"]
                        and (now - self.game_state["in_ball_since"]) >= HOLD_TIME
                        and (now - self.game_state["last_kick_time"]) >= MIN_KICK_INTERVAL
                    ):
                        self.game_state["kick_times"].append(now - self.game_state["ball_spawn_time"])
                        self.game_state["total_kicks"] += 1
                        play_beep()

                        self.game_state["last_hit_time"] = now
                        self.game_state["last_kick_time"] = now
                        self.game_state["ball_spawn_time"] = now
                        self.game_state["must_leave_ball"] = True
                        self.game_state["in_ball"] = False
                        self.game_state["current_side_index"] ^= 1
            else:
                self.game_state["in_ball"] = False
                self.game_state["must_leave_ball"] = False

            self.draw_ball(
                frame,
                int(ball_x),
                int(ball_y),
                now - self.game_state["last_hit_time"] < 0.3
            )

        self.render(frame)

    # ========================================================
    # ===================== DRAW =============================
    # ========================================================

    def draw_ball(self, frame, x, y, glow):
        if glow:
            cv2.circle(frame, (x, y), BALL_RADIUS + 12, (0, 255, 0), -1)

        size = BALL_RADIUS * (2 + (0.2 if glow else 0))
        ball = cv2.resize(self.ball_png, (int(size), int(size)))
        h, w = ball.shape[:2]
        x1, y1 = x - w // 2, y - h // 2

        if x1 < 0 or y1 < 0 or x1 + w > frame.shape[1] or y1 + h > frame.shape[0]:
            return

        alpha = ball[:, :, 3] / 255.0
        for c in range(3):
            frame[y1:y1+h, x1:x1+w, c] = (
                alpha * ball[:, :, c] +
                (1 - alpha) * frame[y1:y1+h, x1:x1+w, c]
            )

    def resizeEvent(self, e):
        self.hud.setGeometry(0, 0, self.width(), self.height())
        self.back_btn.move(self.width() - 160, 20)

    def render(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self.video_label.setPixmap(QPixmap.fromImage(img))


# ============================================================
# ===================== SCORECARD SCREEN =====================
# ============================================================

class ScorecardScreen(QWidget):
    def __init__(self, on_retry, on_menu):
        super().__init__()

        self.on_retry = on_retry
        self.on_menu = on_menu

        # ---------- BACKGROUND ----------
        self.bg = QLabel(self)
        self.bg_pixmap = QPixmap(BACKGROUND_IMAGE)
        self.bg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---------- DARK OVERLAY ----------
        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("""
            QWidget {
                background-color: rgba(2,6,23,200);
            }
        """)

        # ---------- CARD CONTAINER ----------
        self.container = QWidget(self.overlay)
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(2,11,31,220);
                border-radius: 22px;
            }
        """)

        # ---------- CARD LAYOUT ----------
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ---------- TITLE ----------
        title = QLabel("SESSION COMPLETE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 36px;
                font-weight: bold;
                color: #67e8f9;
            }
        """)

        # ---------- STATS ----------
        self.stats_label = QLabel("")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stats_label.setWordWrap(True)
        self.stats_label.setStyleSheet("""
            QLabel {
                font-size: 22px;
                color: #e0f2fe;
            }
        """)

        # ---------- BUTTONS ----------
        self.retry_btn = QPushButton("RETRY")
        self.menu_btn = QPushButton("BACK TO MENU")

        for btn in (self.retry_btn, self.menu_btn):
            btn.setFixedHeight(64)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #020617;
                    color: #e5e7eb;
                    font-size: 20px;
                    font-weight: bold;
                    border-radius: 18px;
                    border: 2px solid #38bdf8;
                }
                QPushButton:hover {
                    background-color: #1e293b;
                }
            """)

        self.retry_btn.clicked.connect(self.on_retry)
        self.menu_btn.clicked.connect(self.on_menu)

        # ---------- ASSEMBLE ----------
        layout.addWidget(title)
        layout.addWidget(self.stats_label)
        layout.addSpacing(10)
        layout.addWidget(self.retry_btn)
        layout.addWidget(self.menu_btn)

    # ---------- UPDATE STATS ----------
    def set_stats(self, game_state, duration):
        kicks = game_state["total_kicks"]
        times = game_state["kick_times"]

        avg = sum(times) / len(times) if times else 0
        best = min(times) if times else 0

        self.stats_label.setText(
            f"Kicks: {kicks}\n"
            f"Average Kick Time: {avg:.2f}s\n"
            f"Best Kick Time: {best:.2f}s\n"
            f"Time Played: {int(duration)}s"
        )

        # Let Qt resize the card based on content
        self.container.adjustSize()

    # ---------- RESIZE ----------
    def resizeEvent(self, e):
        self.bg.setPixmap(
            self.bg_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.bg.resize(self.size())

        self.overlay.setGeometry(0, 0, self.width(), self.height())

        # Center the card dynamically
        self.container.adjustSize()
        self.container.move(
            (self.width() - self.container.width()) // 2,
            (self.height() - self.container.height()) // 2
        )



# ============================================================
# ====================== MAIN WINDOW =========================
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("KickSitStand Trainer")
        self.setWindowState(Qt.WindowState.WindowFullScreen)

        root = QWidget()
        self.setCentralWidget(root)
        self.stack = QStackedLayout(root)

        self.splash = SplashScreen(self.go_to_instructions, self.exit_app)
        self.instructions = InstructionsScreen(self.go_to_posture, self.go_to_splash)
        self.posture = PostureScreen(self.go_to_difficulty, self.go_to_instructions)
        self.difficulty = DifficultyScreen(self.go_to_time_select, self.go_to_posture)
        self.time_select = TimeSelectScreen(self.start_game, self.go_to_difficulty)
        self.game = GameWidget(self.back_from_game, self.show_scorecard)
        self.scorecard = ScorecardScreen(self.retry_game, self.back_to_menu)

        for w in (
            self.splash,
            self.instructions,
            self.posture,
            self.difficulty,
            self.time_select,
            self.game,
            self.scorecard
        ):
            self.stack.addWidget(w)

        self.stack.setCurrentWidget(self.splash)

    def go_to_splash(self):
        self.stack.setCurrentWidget(self.splash)

    def go_to_instructions(self):
        self.stack.setCurrentWidget(self.instructions)

    def go_to_posture(self):
        self.stack.setCurrentWidget(self.posture)

    def go_to_difficulty(self):
        self.stack.setCurrentWidget(self.difficulty)

    def go_to_time_select(self):
        self.stack.setCurrentWidget(self.time_select)

    def start_game(self):
        self.stack.setCurrentWidget(self.game)
        self.game.start()

    def back_from_game(self):
        self.game.stop()
        self.stack.setCurrentWidget(self.time_select)

    def show_scorecard(self, game_state):
        self.scorecard.set_stats(game_state, SESSION_TIME_SECONDS)
        self.stack.setCurrentWidget(self.scorecard)

    def retry_game(self):
        self.start_game()

    def back_to_menu(self):
        self.stack.setCurrentWidget(self.posture)

    def exit_app(self):
        try:
            self.game.stop()
        except Exception:
            pass
        QApplication.quit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.exit_app()


# ============================================================
# ================= APPLICATION ENTRY ========================
# ============================================================

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
