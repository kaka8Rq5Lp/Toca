import sys
import os
import json
import subprocess
import urllib.request
import urllib.parse
import random
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QSlider, QLabel,
                             QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QLineEdit, QMenu, QDialog, QFrame, 
                             QListWidget, QListWidgetItem, QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QPixmap, QImage

PLAYLIST_FILE = "toca_library.json"
DOWNLOAD_FOLDER = "Toca_Downloads"
COVERS_FOLDER = "Toca_Covers"

class SearchThread(QThread):
    results_found = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query, ytdlp_path):
        super().__init__()
        self.query = query
        self.ytdlp_path = ytdlp_path

    def run(self):
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            cmd = [self.ytdlp_path, '--flat-playlist', '--dump-json', f"ytsearch100:{self.query}"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True, startupinfo=startupinfo)

            results = []
            if res.stdout.strip():
                for line in res.stdout.splitlines():
                    if line.strip():
                        data = json.loads(line)
                        video_id = data.get('id', '')
                        raw_url = data.get('url', '')
                        if raw_url and raw_url.startswith('http'):
                            video_url = raw_url
                        elif video_id:
                            video_url = f"https://youtube.com/watch?v={video_id}"
                        else:
                            video_url = raw_url

                        thumbnail = data.get('thumbnail', '')
                        if not thumbnail and video_id:
                            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                        results.append({
                            'title': data.get('title', 'Faixa Online'),
                            'url': video_url,
                            'video_id': video_id,
                            'thumbnail': thumbnail
                        })
            self.results_found.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DownloadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, url, title, output_path, ytdlp_path):
        super().__init__()
        self.url = url
        self.title = title
        self.output_path = output_path
        self.ytdlp_path = ytdlp_path

    def run(self):
        try:
            safe_title = "".join(c for c in self.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            output_template = os.path.join(self.output_path, f"{safe_title}.%(ext)s")

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            cmd = [
                self.ytdlp_path,
                '-f', 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '0',
                '-o', output_template,
                self.url
            ]

            self.progress.emit(f"A descarregar: {self.title}")
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)

            if result.returncode == 0:
                for file in os.listdir(self.output_path):
                    if file.startswith(safe_title) and file.endswith('.mp3'):
                        full_path = os.path.abspath(os.path.join(self.output_path, file))
                        self.finished.emit(True, full_path)
                        return
                self.finished.emit(False, "Ficheiro não encontrado pós-download.")
            else:
                self.finished.emit(False, f"Erro: {result.stderr}")
        except Exception as e:
            self.finished.emit(False, str(e))


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)


class ResultsDialog(QDialog):
    def __init__(self, results, query_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Catálogo de: {query_text.upper()}")
        self.setMinimumSize(750, 600) 
        self.selected_track = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Músicas e Álbuns Encontrados:")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #FFFFFF; margin-bottom: 6px;")
        layout.addWidget(lbl)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: #1A1A1A; border: 1px solid #282828; border-radius: 8px; padding: 5px; }
            QListWidget::item { color: #EAEAEA; padding: 10px 14px; border-bottom: 1px solid #242424; font-size: 13px; }
            QListWidget::item:hover { background-color: #2A2A2A; color: #FFFFFF; border-radius: 4px; }
            QListWidget::item:selected { background-color: #FF6B00; color: #FFFFFF; font-weight: bold; border-radius: 4px; }
        """)
        
        for item in results:
            list_item = QListWidgetItem(item['title'])
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(list_item)
            
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("background-color: transparent; color: #B3B3B3; border: none; font-weight: bold; padding: 8px 16px;")
        btn_cancel.clicked.connect(self.reject)
        
        self.btn_add = QPushButton("Adicionar à Biblioteca")
        self.btn_add.setStyleSheet("background-color: #FF6B00; color: #FFFFFF; border-radius: 16px; font-weight: bold; padding: 8px 24px; border: none;")
        self.btn_add.clicked.connect(self.accept_selection)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(self.btn_add)
        layout.addLayout(btn_layout)
        
        self.list_widget.itemDoubleClicked.connect(self.accept_selection)
        
    def accept_selection(self):
        selected = self.list_widget.currentItem()
        if selected:
            self.selected_track = selected.data(Qt.ItemDataRole.UserRole)
            self.accept()


class TocaApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Toca Premium")
        self.setGeometry(100, 100, 1200, 800)

        if not os.path.exists(DOWNLOAD_FOLDER): os.makedirs(DOWNLOAD_FOLDER)
        if not os.path.exists(COVERS_FOLDER): os.makedirs(COVERS_FOLDER)

        self.library = []
        self.playlists = {"Favoritos": []}
        self.current_index = -1
        self.current_view = "biblioteca"
        self.download_thread = None
        self.search_thread = None
        self.is_muted = False
        self.is_repeat = False
        self.is_shuffle = False
        self.is_circular = False
        self.last_volume = 70
        self.full_track_title = "Nenhuma faixa selecionada"
        self.title_scroll_pos = 0
        self.title_scroll_timer = QTimer(self)
        self.title_scroll_timer.setInterval(350)
        self.title_scroll_timer.timeout.connect(self.scroll_track_title)

        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        self.init_ui()

        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.mediaStatusChanged.connect(self.status_changed)

        self.load_library()
        self.mudar_view("biblioteca")

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QWidget { background-color: #121212; color: #B3B3B3; font-family: 'Segoe UI', Arial, sans-serif; }
            QLabel { color: #FFFFFF; font-weight: 500; }
            QDialog { background-color: #121212; border: 1px solid #282828; }
            
            QFrame#sidebar { background-color: #000000; border: none; }
            QPushButton#btnMenu { background-color: #FF6B00; color: #FFFFFF; border-radius: 6px; text-align: left; padding: 10px 16px; font-weight: 700; font-size: 14px; border: none; }
            QPushButton#btnMenu:hover { color: #FFFFFF; background-color: #FF8533; }
            QPushButton#btnMenu:checked { color: #FFFFFF; background-color: #CC5600; }
            QFrame#stylePanel { background-color: #141414; border: 1px solid #282828; border-radius: 12px; }
            QLabel#styleTitle { color: #FFFFFF; background: transparent; font-size: 13px; font-weight: 800; }
            QLabel#styleImage { background-color: #FF6B00; color: #FFFFFF; border-radius: 18px; font-size: 24px; font-weight: 900; }
            QLabel#loadingLabel { color: #FFB27A; background: transparent; font-size: 12px; font-weight: 800; letter-spacing: 1px; }
            QPushButton#btnStyle { background-color: #242424; color: #EAEAEA; border-radius: 14px; text-align: left; padding: 7px 10px; font-weight: 650; font-size: 12px; border: 1px solid #303030; }
            QPushButton#btnStyle:hover { background-color: #332216; color: #FFFFFF; border: 1px solid #FF6B00; }
            
            QLineEdit { background-color: #242424; color: #FFFFFF; border: 1px solid transparent; border-radius: 18px; padding: 8px 16px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #777777; background-color: #2A2A2A; }
            QPushButton#btnPrimary { background-color: #FF6B00; color: #FFFFFF; border-radius: 20px; font-weight: 700; font-size: 13px; padding: 0 24px; min-height: 40px; border: none; }
            QPushButton#btnPrimary:hover { background-color: #FF8533; }
            
            QTableWidget { background-color: #121212; alternate-background-color: #121212; border: none; gridline-color: transparent; outline: none; }
            QTableWidget::item { background-color: #121212; padding: 10px; border-bottom: 1px solid #1c1c1c; color: #B3B3B3; font-size: 13px; }
            QTableWidget::item:selected { background-color: #FF6B00; color: #FFFFFF; }
            QHeaderView::section { background-color: #121212; color: #B3B3B3; padding: 8px; border: none; font-size: 11px; font-weight: 700; text-transform: uppercase; border-bottom: 1px solid #282828; }
            
            QSlider::groove:horizontal { height: 4px; background: #4F4F4F; border-radius: 2px; }
            QSlider::sub-page:horizontal { background: #FF6B00; border-radius: 2px; }
            QSlider::handle:horizontal { background: #FFFFFF; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        """)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 24, 12, 24)
        sidebar_layout.setSpacing(4)

        self.logo_btn = QPushButton("Toca Studio")
        self.logo_btn.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.logo_btn.setStyleSheet("""
            QPushButton {
                color: #FF6B00; 
                background: transparent; 
                border: none; 
                text-align: left; 
                padding-left: 10px; 
                margin-bottom: 20px;
                font-weight: 800;
            }
            QPushButton:hover {
                color: #FF8533;
            }
        """)
        self.logo_btn.clicked.connect(lambda: self.mudar_view("biblioteca"))
        sidebar_layout.addWidget(self.logo_btn)

        self.btn_menu_biblioteca = QPushButton("📚 A Minha Biblioteca")
        self.btn_menu_biblioteca.setObjectName("btnMenu")
        self.btn_menu_biblioteca.setCheckable(True)
        self.btn_menu_biblioteca.clicked.connect(lambda: self.mudar_view("biblioteca"))
        sidebar_layout.addWidget(self.btn_menu_biblioteca)

        self.btn_menu_favoritos = QPushButton("🧡 Músicas Curtidas")
        self.btn_menu_favoritos.setObjectName("btnMenu")
        self.btn_menu_favoritos.setCheckable(True)
        self.btn_menu_favoritos.clicked.connect(lambda: self.mudar_view("favoritos"))
        sidebar_layout.addWidget(self.btn_menu_favoritos)

        self.btn_menu_downloads = QPushButton("💾 Guardada Offline")
        self.btn_menu_downloads.setObjectName("btnMenu")
        self.btn_menu_downloads.setCheckable(True)
        self.btn_menu_downloads.clicked.connect(lambda: self.mudar_view("downloads"))
        sidebar_layout.addWidget(self.btn_menu_downloads)

        style_panel = QFrame()
        style_panel.setObjectName("stylePanel")
        style_layout = QVBoxLayout(style_panel)
        style_layout.setContentsMargins(12, 12, 12, 12)
        style_layout.setSpacing(7)

        style_image = QLabel("🎶")
        style_image.setObjectName("styleImage")
        style_image.setFixedSize(58, 36)
        style_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        style_layout.addWidget(style_image, alignment=Qt.AlignmentFlag.AlignHCenter)

        style_title = QLabel("🎧 Estilos de Música")
        style_title.setObjectName("styleTitle")
        style_layout.addWidget(style_title)

        current_year = datetime.now().year
        music_styles = [
            ("🇦🇴 Nacionais Angolanas", f"músicas nacionais angolanas {current_year}"),
            ("Kuduro", f"kuduro angolano {current_year}"),
            ("Kizomba", f"kizomba angolana {current_year}"),
            ("Semba", f"semba angolano {current_year}"),
            ("Afro House", f"afro house angolano {current_year}"),
            ("Rap", f"rap {current_year}"),
            ("Outros Estilos", f"músicas africanas populares {current_year}"),
        ]

        for label, query in music_styles:
            style_btn = QPushButton(label)
            style_btn.setObjectName("btnStyle")
            style_btn.clicked.connect(lambda checked=False, q=query: self.search_style(q))
            style_layout.addWidget(style_btn)

        sidebar_layout.addSpacing(16)
        sidebar_layout.addWidget(style_panel)
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(32, 24, 32, 0)
        content_layout.setSpacing(16)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        top_bar.addStretch(1)
        self.online_box = QLineEdit()
        self.online_box.setPlaceholderText("🔍 Procura por artista ou música...")
        self.online_box.setFixedWidth(440)
        self.online_box.returnPressed.connect(self.search_online)
        top_bar.addWidget(self.online_box)

        self.loading_label = QLabel("LOADING...")
        self.loading_label.setObjectName("loadingLabel")
        self.loading_label.hide()
        top_bar.addWidget(self.loading_label)

        top_bar.addStretch(1)
        
        self.btn_add = QPushButton("Importar Ficheiros")
        self.btn_add.setObjectName("btnPrimary")
        self.btn_add.clicked.connect(self.add_songs)
        top_bar.addWidget(self.btn_add)
        content_layout.addLayout(top_bar)

        library_area = QHBoxLayout()
        library_area.setSpacing(22)

        self.track_table = QTableWidget()
        self.track_table.setColumnCount(4)
        self.track_table.setHorizontalHeaderLabels(["#", "Título", "Origem", "Duração"])
        self.track_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.track_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.track_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.track_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.track_table.setColumnWidth(0, 46)
        self.track_table.verticalHeader().setVisible(False)
        self.track_table.verticalHeader().setDefaultSectionSize(44)
        self.track_table.setShowGrid(False)
        self.track_table.setAlternatingRowColors(False)
        self.track_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.track_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.track_table.customContextMenuRequested.connect(self.show_context_menu)
        self.track_table.itemDoubleClicked.connect(self.play_selected)
        library_area.addWidget(self.track_table, 1)

        cover_panel = QFrame()
        cover_panel.setFixedWidth(310)
        cover_panel.setStyleSheet("""
            QFrame {
                background-color: #181818;
                border: 1px solid #282828;
                border-radius: 12px;
            }
        """)
        cover_layout = QVBoxLayout(cover_panel)
        cover_layout.setContentsMargins(16, 16, 16, 16)
        cover_layout.setSpacing(14)

        self.big_cover = QLabel()
        self.big_cover.setFixedSize(278, 278)
        self.big_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.big_cover.setStyleSheet("""
            background-color: #252525;
            border-radius: 10px;
            border: none;
        """)
        self.big_cover.setScaledContents(False)
        cover_layout.addWidget(self.big_cover, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.side_track_title = QLabel("Nenhuma faixa selecionada")
        self.side_track_title.setWordWrap(True)
        self.side_track_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.side_track_title.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")
        cover_layout.addWidget(self.side_track_title)

        self.side_track_status = QLabel("Toca Studio Player")
        self.side_track_status.setWordWrap(True)
        self.side_track_status.setFont(QFont("Segoe UI", 10))
        self.side_track_status.setStyleSheet("color: #B3B3B3; border: none; background: transparent;")
        cover_layout.addWidget(self.side_track_status)
        cover_layout.addStretch()

        library_area.addWidget(cover_panel)
        content_layout.addLayout(library_area, 1)

        player_bar = QFrame()
        player_bar.setStyleSheet("background-color: #181818; border-top: 1px solid #282828; min-height: 100px;")
        player_bar_layout = QHBoxLayout(player_bar)
        player_bar_layout.setContentsMargins(24, 10, 24, 10)

        self.meta_widget = QWidget()
        self.meta_widget.setFixedWidth(300)
        meta_h_layout = QHBoxLayout(self.meta_widget)
        meta_h_layout.setContentsMargins(10, 5, 10, 5)
        meta_h_layout.setSpacing(12)
        meta_h_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_cover = QLabel()
        self.lbl_cover.setFixedSize(60, 60)

        self.lbl_cover.setStyleSheet("background-color: #282828; border-radius: 4px;")
        self.lbl_cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cover.setScaledContents(False)
        meta_h_layout.addWidget(self.lbl_cover)

        meta_layout = QVBoxLayout()
        self.lbl_track = QLabel("Nenhuma faixa selecionada")
        self.lbl_track.setFixedWidth(210)
        self.lbl_track.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.lbl_track.setStyleSheet("color: #FFFFFF;")
        self.lbl_artist = QLabel("Toca Studio Player")
        self.lbl_artist.setFont(QFont("Segoe UI", 10))
        self.lbl_artist.setStyleSheet("color: #B3B3B3;")
        meta_layout.addWidget(self.lbl_track)
        meta_layout.addWidget(self.lbl_artist)
        meta_h_layout.addLayout(meta_layout)
        
        player_bar_layout.addWidget(self.meta_widget, 1)

        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.setSpacing(6)

        controls_layout = QHBoxLayout()
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        controls_layout.setSpacing(16)

        self.btn_shuffle = QPushButton("🔀")
        self.btn_shuffle.setFixedSize(34, 34)
        self.btn_shuffle.setToolTip("Aleatório")
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)

        self.btn_prev = QPushButton("🡸")
        self.btn_prev.setStyleSheet("background: transparent; font-size: 22px; color: #B3B3B3; border: none; font-weight: bold;")
        self.btn_prev.clicked.connect(self.prev_song)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(44, 44)
        self.btn_play.setStyleSheet("""
            QPushButton { background-color: #FF6B00; color: #FFFFFF; border-radius: 22px; font-size: 18px; font-weight: bold; border: none; padding-left: 2px; }
            QPushButton:hover { background-color: #FF8533; }
        """)
        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_next = QPushButton("🡺")
        self.btn_next.setStyleSheet("background: transparent; font-size: 22px; color: #B3B3B3; border: none; font-weight: bold;")
        self.btn_next.clicked.connect(self.next_song)

        self.btn_repeat = QPushButton("🔁")
        self.btn_repeat.setFixedSize(34, 34)
        self.btn_repeat.setToolTip("Repetir música")
        self.btn_repeat.clicked.connect(self.toggle_repeat)

        self.btn_circular = QPushButton("∞")
        self.btn_circular.setFixedSize(34, 34)
        self.btn_circular.setToolTip("Lista circular")
        self.btn_circular.clicked.connect(self.toggle_circular)

        controls_layout.addWidget(self.btn_shuffle)
        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_repeat)
        controls_layout.addWidget(self.btn_circular)
        center_layout.addLayout(controls_layout)

        progress_layout = QHBoxLayout()
        self.lbl_pos = QLabel("0:00")
        self.lbl_pos.setFont(QFont("Segoe UI", 10))
        self.lbl_pos.setStyleSheet("color: #A7A7A7;")
        self.slider_progress = ClickableSlider(Qt.Orientation.Horizontal)
        self.slider_progress.sliderMoved.connect(self.seek_position)
        self.lbl_dur = QLabel("0:00")
        self.lbl_dur.setFont(QFont("Segoe UI", 10))
        self.lbl_dur.setStyleSheet("color: #A7A7A7;")
        
        progress_layout.addWidget(self.lbl_pos)
        progress_layout.addWidget(self.slider_progress)
        progress_layout.addWidget(self.lbl_dur)
        center_layout.addLayout(progress_layout)
        player_bar_layout.addLayout(center_layout, 2)

        volume_layout = QHBoxLayout()
        volume_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setFixedSize(34, 34)
        self.btn_mute.setToolTip("Silenciar")
        self.btn_mute.clicked.connect(self.toggle_mute)
        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(0, 100)
        self.slider_volume.setValue(70)
        self.slider_volume.setFixedWidth(100)
        self.slider_volume.valueChanged.connect(self.change_volume)
        volume_layout.addWidget(self.btn_mute)
        volume_layout.addWidget(self.slider_volume)
        player_bar_layout.addLayout(volume_layout, 1)

        content_layout.addWidget(player_bar)
        main_layout.addWidget(content_widget)
        self.clear_cover()
        self.update_mode_buttons()

    def clear_cover(self):
        small_pixmap = QPixmap(60, 60)
        small_pixmap.fill(QColor("#282828"))
        self.lbl_cover.setPixmap(small_pixmap)

        big_pixmap = QPixmap(278, 278)
        big_pixmap.fill(QColor("#252525"))
        self.big_cover.setPixmap(big_pixmap)
        self.side_track_title.setText("Nenhuma faixa selecionada")
        self.side_track_status.setText("Toca Studio Player")

    def mode_button_style(self, active=False, font_size=15):
        color = "#FF6B00" if active else "#B3B3B3"
        background = "#2A2A2A" if active else "transparent"
        return f"""
            QPushButton {{
                background-color: {background};
                color: {color};
                border: none;
                border-radius: 17px;
                font-size: {font_size}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #2A2A2A;
                color: #FFFFFF;
            }}
        """

    def update_mode_buttons(self):
        self.btn_shuffle.setStyleSheet(self.mode_button_style(self.is_shuffle, 14))
        self.btn_repeat.setStyleSheet(self.mode_button_style(self.is_repeat, 14))
        self.btn_circular.setStyleSheet(self.mode_button_style(self.is_circular, 18))
        self.btn_mute.setText("🔇" if self.is_muted else "🔊")
        self.btn_mute.setStyleSheet(self.mode_button_style(self.is_muted, 14))

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        self.update_mode_buttons()

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        self.update_mode_buttons()

    def toggle_circular(self):
        self.is_circular = not self.is_circular
        self.update_mode_buttons()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.last_volume = self.slider_volume.value() or self.last_volume
            self.audio_output.setVolume(0)
        else:
            restored_volume = self.last_volume if self.last_volume > 0 else 70
            self.slider_volume.setValue(restored_volume)
            self.audio_output.setVolume(restored_volume / 100)
        self.update_mode_buttons()

    def start_title_scroll(self, title):
        self.full_track_title = title or "Nenhuma faixa selecionada"
        self.title_scroll_pos = 0
        self.lbl_track.setToolTip(self.full_track_title)
        self.side_track_title.setText(self.full_track_title)
        self.side_track_title.setToolTip(self.full_track_title)
        if len(self.full_track_title) > 24:
            self.title_scroll_timer.start()
            self.scroll_track_title()
        else:
            self.title_scroll_timer.stop()
            self.lbl_track.setText(self.full_track_title)

    def scroll_track_title(self):
        title = self.full_track_title
        if len(title) <= 24:
            self.lbl_track.setText(title)
            return

        scrolling_text = f"{title}     "
        start = self.title_scroll_pos % len(scrolling_text)
        visible = (scrolling_text + scrolling_text)[start:start + 28]
        self.lbl_track.setText(visible)
        self.title_scroll_pos += 1

    def safe_cover_name(self, title):
        safe_name = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
        safe_name = safe_name.replace(" ", "_")
        return safe_name[:80] or "cover"

    def download_cover_image(self, image_url, title):
        if not image_url:
            return ""

        image_urls = []
        youtube_id = self.extract_youtube_id(image_url)
        if youtube_id:
            image_urls.extend([
                f"https://i.ytimg.com/vi/{youtube_id}/maxresdefault.jpg",
                f"https://i.ytimg.com/vi/{youtube_id}/sddefault.jpg",
                f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg",
                f"https://i.ytimg.com/vi/{youtube_id}/mqdefault.jpg",
            ])
        image_urls.append(image_url)

        for candidate_url in dict.fromkeys(image_urls):
            try:
                parsed = urllib.parse.urlparse(candidate_url)
                ext = os.path.splitext(parsed.path)[1].lower()
                if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                    ext = ".jpg"

                cover_local = os.path.abspath(os.path.join(COVERS_FOLDER, f"{self.safe_cover_name(title)}{ext}"))
                request = urllib.request.Request(
                    candidate_url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    },
                )

                with urllib.request.urlopen(request, timeout=15) as response:
                    image_data = response.read()

                pixmap = QPixmap()
                if not pixmap.loadFromData(image_data):
                    continue

                pixmap.save(cover_local)
                return cover_local
            except Exception as e:
                print(f"Erro ao descarregar capa {candidate_url}: {e}")

        return ""

    def get_best_thumbnail(self, video_url, fallback_thumbnail=""):
        youtube_id = self.extract_youtube_id(video_url)
        if not fallback_thumbnail and youtube_id:
            fallback_thumbnail = f"https://i.ytimg.com/vi/{youtube_id}/hqdefault.jpg"

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            cmd = [self.get_ytdlp_path(), '--dump-single-json', '--skip-download', video_url]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, startupinfo=startupinfo)
            data = json.loads(result.stdout)

            thumbnails = data.get("thumbnails", [])
            if thumbnails:
                thumbnails = sorted(thumbnails, key=lambda item: item.get("width", 0) * item.get("height", 0))
                return thumbnails[-1].get("url", fallback_thumbnail)

            return data.get("thumbnail", fallback_thumbnail)
        except Exception as e:
            print(f"Erro ao obter thumbnail: {e}")
            return fallback_thumbnail

    def extract_youtube_id(self, url):
        if not url:
            return ""

        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.netloc.endswith("youtu.be"):
                return parsed.path.strip("/")

            if "ytimg.com" in parsed.netloc and "/vi/" in parsed.path:
                return parsed.path.split("/vi/", 1)[1].split("/", 1)[0]

            query = urllib.parse.parse_qs(parsed.query)
            if "v" in query and query["v"]:
                return query["v"][0]

            if "/shorts/" in parsed.path:
                return parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]

            if "/embed/" in parsed.path:
                return parsed.path.split("/embed/", 1)[1].split("/", 1)[0]
        except Exception:
            pass

        return ""

    def ensure_track_cover(self, track):
        if self.set_cover_from_path(track.get('cover_path', '')):
            return True

        thumbnail_url = track.get('thumbnail_url', '')
        if not thumbnail_url:
            thumbnail_url = self.get_best_thumbnail(track.get('original_url', ''), track.get('thumbnail', ''))

        cover_path = self.download_cover_image(thumbnail_url, track.get('name', 'cover'))
        if not cover_path:
            return False

        track['thumbnail_url'] = thumbnail_url
        track['cover_path'] = cover_path
        self.save_library()
        return self.set_cover_from_path(cover_path)

    def set_cover_from_path(self, cover_path):
        if not cover_path or not os.path.exists(cover_path):
            self.clear_cover()
            return False

        pixmap = QPixmap(cover_path)
        if pixmap.isNull():
            self.clear_cover()
            return False

        self.lbl_cover.setPixmap(
            pixmap.scaled(
                60, 60,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        self.big_cover.setPixmap(
            pixmap.scaled(
                278, 278,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )
        return True

    def seek_position(self, position):
        self.player.setPosition(position)

    def mudar_view(self, view):
        self.current_view = view
        self.btn_menu_biblioteca.setChecked(view == "biblioteca")
        self.btn_menu_favoritos.setChecked(view == "favoritos")
        self.btn_menu_downloads.setChecked(view == "downloads")
        self.refresh_track_table()

    def ms_to_time(self, ms):
        if ms <= 0: return "0:00"
        segundos = int(ms / 1000)
        m, s = divmod(segundos, 60)
        return f"{m}:{s:02d}"

    def save_library(self):
        try:
            data = {"library": self.library, "playlists": self.playlists}
            with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Erro ao guardar biblioteca: {e}")

    def load_library(self):
        if os.path.exists(PLAYLIST_FILE):
            try:
                with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.library = data.get("library", [])
                    self.playlists = data.get("playlists", {"Favoritos": []})
                self.refresh_track_table()
            except Exception as e:
                print(f"Erro ao carregar biblioteca: {e}")

    def refresh_track_table(self):
        self.track_table.clearContents()
        if self.current_view == "biblioteca": self.current_list = self.library
        elif self.current_view == "favoritos": self.current_list = [t for t in self.library if t.get('favorite', False)]
        elif self.current_view == "downloads": self.current_list = [t for t in self.library if t.get('is_downloaded', False)]

        current_track = self.library[self.current_index] if 0 <= self.current_index < len(self.library) else None
        self.track_table.setRowCount(len(self.current_list))
        playing_view_row = -1
        for row, track in enumerate(self.current_list):
            item_num = QTableWidgetItem(str(row + 1))
            item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            prefix = "🧡 " if track.get('favorite', False) else ""
            item_title = QTableWidgetItem(f"{prefix}{track['name']}")
            
            origem = "Offline" if track.get('is_downloaded') else "Nuvem 🌐"
            item_origin = QTableWidgetItem(origem)
            item_dur = QTableWidgetItem(track.get('duration_str', "--:--"))

            is_playing_row = track is current_track
            if is_playing_row:
                playing_view_row = row
            row_bg = QColor("#FF6B00" if is_playing_row else "#121212")
            normal_text = QColor("#FFFFFF" if is_playing_row else "#B3B3B3")
            title_text = QColor("#FFFFFF" if is_playing_row else "#EAEAEA")

            for item in (item_num, item_title, item_origin, item_dur):
                item.setBackground(row_bg)
                item.setForeground(normal_text)
            item_title.setForeground(title_text)
            if is_playing_row:
                item_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))

            self.track_table.setItem(row, 0, item_num)
            self.track_table.setItem(row, 1, item_title)
            self.track_table.setItem(row, 2, item_origin)
            self.track_table.setItem(row, 3, item_dur)

        if playing_view_row >= 0:
            self.track_table.selectRow(playing_view_row)
            self.track_table.scrollToItem(self.track_table.item(playing_view_row, 1))
        else:
            self.track_table.clearSelection()

    def get_ytdlp_path(self):
        user_path = os.path.expanduser('~')
        fallback_path = os.path.join(user_path, 'AppData', 'Local', 'Python', 'pythoncore-3.14-64', 'Scripts', 'yt-dlp.exe')
        return fallback_path if os.path.exists(fallback_path) else 'yt-dlp'

    def add_songs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Selecionar Faixas Locais", "", "Áudio (*.mp3 *.wav *.m4a *.flac)")
        if files:
            for file in files:
                caminho = os.path.abspath(file)
                if not any(t['path'] == caminho for t in self.library):
                    self.library.append({
                        'path': caminho, 'name': os.path.splitext(os.path.basename(caminho))[0],
                        'favorite': False, 'is_online': False, 'is_downloaded': True, 'duration_str': "Local",
                        'cover_path': ''
                    })
            self.refresh_track_table()
            self.save_library()

    def search_online(self):
        query = self.online_box.text().strip()
        if not query: return

        if self.search_thread and self.search_thread.isRunning():
            self.loading_label.setText("LOADING...")
            self.loading_label.show()
            return

        self.loading_label.setText("LOADING...")
        self.loading_label.show()

        self.search_thread = SearchThread(query, self.get_ytdlp_path())
        self.search_thread.results_found.connect(lambda res: self.search_finished(res, query))
        self.search_thread.error_occurred.connect(self.search_error)
        self.search_thread.start()

    def search_style(self, query):
        self.online_box.setText(query)
        self.search_online()

    def search_finished(self, results, query):
        self.loading_label.hide()
        if self.search_thread:
            self.search_thread.deleteLater()
            self.search_thread = None
        if results:
            dialog = ResultsDialog(results, query, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_track:
                chosen = dialog.selected_track
                
                self.lbl_track.setText("A gerar stream link...")
                QApplication.processEvents()
                
                try:
                    startupinfo = None
                    if os.name == 'nt':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                    cmd_stream = [self.get_ytdlp_path(), '-g', '-f', 'bestaudio', chosen['url']]
                    res_stream = subprocess.run(cmd_stream, capture_output=True, text=True, check=True, startupinfo=startupinfo)
                    stream_url = res_stream.stdout.strip()
                    
                    thumbnail_url = self.get_best_thumbnail(chosen['url'], chosen.get('thumbnail', ''))
                    cover_local = self.download_cover_image(thumbnail_url, chosen['title'])

                    if stream_url:
                        self.library.append({
                            'path': stream_url, 'name': chosen['title'],
                            'favorite': False, 'is_online': True, 'is_downloaded': False, 'original_url': chosen['url'],
                            'duration_str': "Stream", 'cover_path': cover_local, 'thumbnail_url': thumbnail_url
                        })
                        self.online_box.clear()
                        self.mudar_view("biblioteca")
                        self.save_library()
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível obter o link de streaming: {e}")
        else:
            QMessageBox.information(self, "Toca", "Não encontrámos um catálogo para esse artista.")

    def search_error(self, err_msg):
        self.loading_label.hide()
        if self.search_thread:
            self.search_thread.deleteLater()
            self.search_thread = None
        QMessageBox.critical(self, "Erro de Conexão", f"Falha ao pesquisar catálogo: {err_msg}")

    def show_context_menu(self, position):
        item = self.track_table.itemAt(position)
        if not item:
            menu = QMenu(self)
            act_refresh = QAction("🔄 Actualizar", self)
            act_refresh.triggered.connect(self.refresh_track_table)
            menu.addAction(act_refresh)

            act_load = QAction("📂 Carregar músicas", self)
            act_load.triggered.connect(self.add_songs)
            menu.addAction(act_load)

            menu.exec(self.track_table.viewport().mapToGlobal(position))
            return

        row = self.track_table.row(item)
        
        track_ref = self.current_list[row]
        actual_row = self.library.index(track_ref)

        menu = QMenu(self)
        act_play = QAction("▶ Tocar Agora", self)
        act_play.triggered.connect(lambda: self.play_from_row(actual_row))
        menu.addAction(act_play)

        if track_ref.get('is_online') and not track_ref.get('is_downloaded'):
            act_dl = QAction("💾 Descarregar Offline", self)
            act_dl.triggered.connect(lambda: self.download_track(actual_row))
            menu.addAction(act_dl)

        is_fav = track_ref.get('favorite', False)
        act_fav = QAction("💔 Remover dos Favoritos" if is_fav else "🧡 Adicionar aos Favoritos", self)
        act_fav.triggered.connect(lambda: self.toggle_favorite_row(actual_row))
        menu.addAction(act_fav)

        act_del = QAction("🗑 Apagar", self)
        act_del.triggered.connect(lambda: self.delete_row(actual_row))
        menu.addAction(act_del)
        menu.exec(self.track_table.viewport().mapToGlobal(position))

    def download_track(self, row):
        track = self.library[row]
        url = track.get('original_url')
        if not url: return

        if self.download_thread and self.download_thread.isRunning():
            self.loading_label.setText("A GUARDAR...")
            self.loading_label.show()
            return

        self.loading_label.setText("A GUARDAR...")
        self.loading_label.show()

        self.download_thread = DownloadThread(url, track['name'], DOWNLOAD_FOLDER, self.get_ytdlp_path())
        self.download_thread.progress.connect(lambda msg: self.loading_label.setText("A GUARDAR..."))
        self.download_thread.finished.connect(lambda s, r: self.download_finished(row, s, r))
        self.download_thread.start()

    def download_finished(self, row, success, result_path):
        self.loading_label.hide()
        if success and row < len(self.library):
            self.library[row]['path'] = result_path
            self.library[row]['is_online'] = False
            self.library[row]['is_downloaded'] = True
            self.library[row]['duration_str'] = "Guardado"
            self.save_library()
            self.refresh_track_table()
        elif not success:
            QMessageBox.warning(self, "Toca", f"Não foi possível guardar a música: {result_path}")

        if self.download_thread:
            self.download_thread.deleteLater()
            self.download_thread = None

    def play_from_row(self, row):
        self.current_index = row
        self.play_current()

    def toggle_favorite_row(self, row):
        self.library[row]['favorite'] = not self.library[row].get('favorite', False)
        self.save_library()
        self.refresh_track_table()

    def delete_row(self, row):
        if row == self.current_index:
            self.player.stop()
            self.current_index = -1
        self.library.pop(row)
        self.save_library()
        self.refresh_track_table()

    def play_selected(self):
        row = self.track_table.currentRow()
        if row < 0: return
        target = self.current_list[row]
        self.current_index = self.library.index(target)
        self.play_current()

    def play_current(self):
        if 0 <= self.current_index < len(self.library):
            track = self.library[self.current_index]
            self.start_title_scroll(track['name'])
            self.lbl_artist.setText("A reproduzir...")
            origem = "Guardada offline" if track.get('is_downloaded') else "A tocar da nuvem"
            self.side_track_status.setText(origem)
            self.refresh_track_table()
            
            self.ensure_track_cover(track)

            try:
                path = track['path']
                url = QUrl.fromLocalFile(path) if os.path.exists(path) else QUrl(path)
                self.player.setSource(url)
                self.player.play()
                self.btn_play.setText("❙❙")
                self.btn_play.setStyleSheet("QPushButton { background-color: #FF6B00; color: #FFFFFF; border-radius: 22px; font-size: 16px; font-weight: bold; border: none; padding-left: 0px; } QPushButton:hover { background-color: #FF8533; }")
            except Exception as e:
                print(f"Erro Player: {e}")

    def toggle_play(self):
        from PyQt6.QtMultimedia import QMediaPlayer
        if not self.library: return
        if self.current_index == -1:
            self.current_index = 0
            self.play_current()
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
            self.btn_play.setStyleSheet("QPushButton { background-color: #FF6B00; color: #FFFFFF; border-radius: 22px; font-size: 18px; font-weight: bold; border: none; padding-left: 2px; } QPushButton:hover { background-color: #FF8533; }")
        else:
            self.player.play()
            self.btn_play.setText("❙❙")
            self.btn_play.setStyleSheet("QPushButton { background-color: #FF6B00; color: #FFFFFF; border-radius: 22px; font-size: 16px; font-weight: bold; border: none; padding-left: 0px; } QPushButton:hover { background-color: #FF8533; }")

    def next_song(self):
        if not self.library:
            return

        if self.is_shuffle and len(self.library) > 1:
            choices = [i for i in range(len(self.library)) if i != self.current_index]
            self.current_index = random.choice(choices)
            self.play_current()
            return

        if self.current_index < len(self.library) - 1:
            self.current_index += 1
            self.play_current()
        elif self.is_circular:
            self.current_index = 0
            self.play_current()

    def prev_song(self):
        if not self.library:
            return

        if self.current_index > 0:
            self.current_index -= 1
            self.play_current()
        elif self.is_circular:
            self.current_index = len(self.library) - 1
            self.play_current()

    def change_volume(self, value):
        if value > 0:
            self.last_volume = value
        if self.is_muted and value > 0:
            self.is_muted = False
            self.update_mode_buttons()
        self.audio_output.setVolume(0 if self.is_muted else value / 100)

    def position_changed(self, position):
        if not self.slider_progress.isSliderDown():
            self.slider_progress.setValue(position)
        self.lbl_pos.setText(self.ms_to_time(position))

    def duration_changed(self, duration):
        self.slider_progress.setRange(0, duration)
        self.lbl_dur.setText(self.ms_to_time(duration))

    def status_changed(self, status):
        from PyQt6.QtMultimedia import QMediaPlayer
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_repeat:
                self.player.setPosition(0)
                self.player.play()
            else:
                self.next_song()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = TocaApp()
    player.show()
    sys.exit(app.exec())
