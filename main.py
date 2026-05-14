import gc
import objgraph
import zipfile
import shutil
import subprocess
import sys, os, importlib.util, json
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from AppKit import *
import objc

try:
    info = NSBundle.mainBundle().infoDictionary()
    info['LSUIElement'] = '1'
except Exception:
    pass

def get_theme(is_dark):
    bg = "rgba(30, 30, 30, 240)" if is_dark else "rgba(245, 245, 245, 240)"
    text = "#ffffff" if is_dark else "#000000"
    nav_text = "rgba(255, 255, 255, 120)" if is_dark else "rgba(0, 0, 0, 120)"
    border = "rgba(255, 255, 255, 30)" if is_dark else "rgba(0, 0, 0, 30)"
    item_hover = "rgba(255, 255, 255, 20)" if is_dark else "rgba(0, 0, 0, 10)"
    scroll_handle = "rgba(255, 255, 255, 40)" if is_dark else "rgba(0, 0, 0, 40)"
    scroll_hover = "rgba(255, 255, 255, 70)" if is_dark else "rgba(0, 0, 0, 70)"
    
    return f"""
    QPushButton#SideBtn {{
        text-align: left; background: transparent; border: none;
        color: {nav_text}; font-family: 'Menlo'; font-size: 14px; 
        padding: 4px 12px; border-radius: 8px;
    }}
    QPushButton#SideBtn:checked {{ color: {text};}}
    
    QLabel#PluginTitle {{ 
        font-size: 42px; font-weight: bold; color: {text}; 
        font-family: 'Menlo'; 
    }}
    
    QPushButton#BottomNavBtn {{
        color: {nav_text}; background: transparent; border: none;
        font-family: 'Menlo'; font-size: 13px; padding: 5px 10px;
        border-bottom: 2px solid transparent;
    }}
    QPushButton#BottomNavBtn:checked {{ 
        color: {text}; border-bottom: 2px solid {text}; 
    }}
        QScrollBar:vertical {{
        border: none;
        background: transparent;
        width: 8px;
        margin: 0px 2px 0px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {scroll_handle};
        border-radius: 4px;
        min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {scroll_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        background: none;
    }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: none;
    }}
    QScrollBar:horizontal {{
        height: 0px;
    }}
"""

class KToast(QWidget):
    def __init__(self, text, manager_list):
        super().__init__()
        self.manager_list = manager_list
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.setFixedSize(400, 50)
        
        self.root = QFrame(self)
        self.root.setObjectName("MainContainer")
        self.root.setFixedSize(400, 40)
        
        layout = QHBoxLayout(self.root)
        layout.setContentsMargins(20, 0, 20, 0)
        self.label = QLabel(text.lower())
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.anim_group = QParallelAnimationGroup(self)
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        
        for a in [self.pos_anim, self.opacity_anim]:
            a.setDuration(300)
            a.setEasingCurve(QEasingCurve.Type.OutQuint)
            self.anim_group.addAnimation(a)
            
        self.is_hiding = False
        self.update_theme()

    def update_position(self, index):
        screen = QApplication.primaryScreen().availableGeometry()

        target_y = screen.height() - 80 - (index * 55)
        target_x = (screen.width() - self.width()) // 2
        
        self.pos_anim.setEndValue(QPoint(target_x, target_y))
        self.opacity_anim.setEndValue(1.0)
        self.anim_group.start()

    def hide_anim(self):
        if self.is_hiding: return
        self.is_hiding = True
        self.opacity_anim.setEndValue(0.0)
        self.anim_group.start()
        self.anim_group.finished.connect(self.close)

    def closeEvent(self, event):
        if self in self.manager_list:
            self.manager_list.remove(self)
        super().closeEvent(event)
    

    def update_theme(self):
        is_dark = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark"
        bg = "rgba(25, 25, 25, 180)" if is_dark else "rgba(240, 240, 240, 180)"
        text = "#ffffff" if is_dark else "#000000"
        border = "rgba(255, 255, 255, 25)" if is_dark else "rgba(0, 0, 0, 25)"
        
        self.setStyleSheet(f"""
            QFrame#MainContainer {{
                background: {bg};
                border-radius: 20px;
                border: 1px solid {border};
            }}
            QLabel {{ color: {text}; font-family: 'Menlo'; font-size: 13px; }}
        """)

    def _apply_native_flags(self):
        try:
            from AppKit import NSApp, NSStatusWindowLevel
            for window in NSApp.windows():
                if window.isVisible() and window.frame().size.width == self.width():
                    window.setLevel_(NSStatusWindowLevel + 1)
                    window.setHidesOnDeactivate_(False)
                    behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces | 
                                NSWindowCollectionBehaviorStationary | 
                                NSWindowCollectionBehaviorIgnoresCycle)
                    window.setCollectionBehavior_(behavior)
        except: pass

    def show_anim(self):
        self.is_hiding = False

        self.setWindowOpacity(0.0)
        self.setVisible(True) 

        try:
            from AppKit import NSApp
            for window in NSApp.windows():
                if window.isVisible() and window.frame().size.width == self.width():
                    window.orderFrontRegardless()
                    break
        except:
            pass

        QTimer.singleShot(10, self._apply_native_flags)
        
        self.pos_anim.setStartValue(self.start_pos)
        self.pos_anim.setEndValue(self.end_pos)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        
        self.anim_group.start()
        QTimer.singleShot(3000, self.hide_anim)

    def _on_anim_finished(self):
        if self.is_hiding:
            self.close()

class LogEmitter(QObject):
    sig_log = pyqtSignal(str)

class LogStream:
    def __init__(self, emitter):
        self.emitter = emitter

    def write(self, text):
        if text.strip():
            self.emitter.sig_log.emit(text.strip())

    def flush(self):
        pass

class InstallWorker(QThread):
    finished = pyqtSignal(int)
    
    def __init__(self, dep_mgr, packages):
        super().__init__()
        self.dep_mgr = dep_mgr
        self.packages = packages

    def run(self):
        installed_count = 0
        for pkg in self.packages:
            print(f"dependency manager: installing: {pkg}")
            cmd = self.dep_mgr.pip_cmd + ["install", pkg]
            
            if sys.prefix == sys.base_prefix:
                cmd.extend(["--user", "--break-system-packages"])

            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                installed_count += 1
            else:
                print(f"dependency manager: failed to install {pkg}: {res.stderr}")
        
        self.finished.emit(installed_count)

class PluginCard(QPushButton):
    def __init__(self, name, is_active=False):
        super().__init__(name.lower())
        self.setObjectName("SideBtn")
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)

class PluginManager(QMainWindow):
    def __init__(self, ktools):
        super().__init__()
        self.ktools = ktools

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(780, 500)
        
        screen = QApplication.primaryScreen().availableGeometry()
        self.end_pos = QPoint(screen.center().x() - 390, screen.center().y() - 250)
        self.start_pos = QPoint(self.end_pos.x(), self.end_pos.y() - 40)

        self.root = QWidget()
        self.root.setObjectName("MainContainer")
        
        self.reload_btn = QPushButton("reload plugins")
        self.reload_btn.setObjectName("ActionBtn")
        self.reload_btn.clicked.connect(self.ktools.reload_all)

        self.import_btn = QPushButton("import plugins")
        self.import_btn.setObjectName("ActionBtn")
        self.import_btn.clicked.connect(self.handle_import)

        self.content_area = QStackedWidget()
        self.plugin_title = QLabel("select a plugin")
        self.plugin_details = QLabel("")
        self.plugin_details.setWordWrap(True)
        self.plugin_details.setObjectName("DetailsText")
        self.plugin_details.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.nav_btns = []
        for i, name in enumerate(["plugins manager", "ktools settings", "logs"]):
            btn = QPushButton(name)
            btn.setObjectName("BottomNavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda ch, idx=i: self.set_main_tab(idx))
            self.nav_btns.append(btn)

        self.outer_vbox = QVBoxLayout(self.root)
        self.outer_vbox.setContentsMargins(25, 25, 25, 20)

        self.top_hbox = QHBoxLayout()
        self.top_hbox.setSpacing(0)

        self.sidebar_container = QWidget()
        self.sidebar_container.setFixedWidth(200)
        self.sidebar_vbox = QVBoxLayout(self.sidebar_container)
        self.sidebar_vbox.setContentsMargins(0, 0, 15, 0)
        self.sidebar_vbox.setSpacing(8)
        
        self.plugin_list_layout = QVBoxLayout()
        self.plugin_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.side_scroll = QScrollArea()
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.side_scroll.setStyleSheet("background: transparent;")

        self.side_content = QWidget()
        self.plugin_list_layout = QVBoxLayout(self.side_content)
        self.plugin_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.plugin_list_layout.setContentsMargins(0, 0, 5, 0)
        self.plugin_list_layout.setSpacing(8)

        self.side_scroll.setWidget(self.side_content)

        self.sidebar_vbox.addWidget(self.side_scroll)
        self.sidebar_vbox.addWidget(self.reload_btn)
        self.sidebar_vbox.addWidget(self.import_btn)

        self.plugin_details_scroll = QScrollArea()
        self.plugin_details_scroll.setWidgetResizable(True)
        self.plugin_details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.plugin_details_scroll.setStyleSheet("background: transparent;")

        self.plugin_info_view = QWidget()
        self.plugin_info_view.setObjectName("PluginDetailsWidget")
        info_layout = QVBoxLayout(self.plugin_info_view)
        info_layout.setContentsMargins(30, 0, 15, 0) 
        info_layout.setSpacing(15)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.plugin_title.setObjectName("PluginTitle")
        info_layout.addWidget(self.plugin_title)
        info_layout.addWidget(self.plugin_details)
        
        self.settings_box = QVBoxLayout() 
        self.settings_box.setSpacing(10)
        self.settings_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        info_layout.addLayout(self.settings_box)
        
        info_layout.addStretch()

        self.plugin_details_scroll.setWidget(self.plugin_info_view)

        self.content_area.addWidget(self.plugin_details_scroll)

        self.settings_page = self.setup_settings_page()
        self.content_area.addWidget(self.settings_page)

        self.log_view = QWidget()
        log_layout = QVBoxLayout(self.log_view)
        log_layout.setContentsMargins(30, 0, 0, 0)
        
        self.log_display = QLabel("system logs initialized...\n")
        self.log_display.setObjectName("DetailsText")
        self.log_display.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.log_display.setWordWrap(True)
        
        log_scroll = QScrollArea()
        log_scroll.setWidgetResizable(True)
        log_scroll.setFrameShape(QFrame.Shape.NoFrame)
        log_scroll.setStyleSheet("background: transparent;")
        log_scroll.setWidget(self.log_display)
        
        log_layout.addWidget(log_scroll)
        self.content_area.addWidget(self.log_view)

        self.top_hbox.addWidget(self.sidebar_container, 1)
        self.top_hbox.addWidget(self.content_area, 3)

        self.nav_hbox = QHBoxLayout()
        self.nav_hbox.setContentsMargins(0, 15, 0, 0)
        for btn in self.nav_btns: self.nav_hbox.addWidget(btn)
        self.nav_hbox.addStretch()

        self.outer_vbox.addLayout(self.top_hbox)
        self.outer_vbox.addLayout(self.nav_hbox)

        self.setCentralWidget(self.root)

        self.anim_group = QParallelAnimationGroup()
        self.pos_anim = QPropertyAnimation(self, b"pos")
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity")
        for a in [self.pos_anim, self.opacity_anim]:
            a.setDuration(150)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(a)
        
        self.plugin_group = QButtonGroup(self)
        self.plugin_group.setExclusive(True)
        
        self.is_hiding = False
        self.installEventFilter(self)
        self.update_theme()

    def set_main_tab(self, idx):
        self.content_area.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_btns):
            b.setChecked(i == idx)

        self.sidebar_container.setVisible(idx == 0)

        if idx == 1:
            self.refresh_deps_tab()

    def refresh_list(self):
        while self.plugin_list_layout.count():
            item = self.plugin_list_layout.takeAt(0)
            if item.widget(): 
                self.plugin_group.removeButton(item.widget())
                item.widget().deleteLater()
            
        plugins = self.ktools.get_plugins_info()

        for i, data in enumerate(plugins):
            btn = PluginCard(data.get('name', 'unknown'), is_active=(i==0))

            self.plugin_group.addButton(btn)
            
            btn.clicked.connect(lambda checked, d=data: self.show_plugin_details(d))
            self.plugin_list_layout.addWidget(btn)
        
        if plugins: 
            self.show_plugin_details(plugins[0])

    def show_plugin_details(self, data):
        self.plugin_title.setText(data.get('name', 'unknown').lower())
        
        details = (
            f"author: {data.get('author', 'kriaiss')}\n"
            f"version: {data.get('version', '1.0.0')}\n"
            f"dependencies: {', '.join(data.get('deps', []))}\n\n"
            f"description:\n{data.get('desc', 'no description')}\n"
        )
        self.plugin_details.setText(details)

        plugin_instance = self.ktools.plugins.get(data.get('id'))

        while self.settings_box.count():
            item = self.settings_box.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for setting_name in data.get('settings', []):
            s_btn = QPushButton(setting_name.lower())
            s_btn.setObjectName("ActionBtn")
            s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            if plugin_instance:
                s_btn.clicked.connect(lambda checked, s=setting_name, p=plugin_instance: 
                                      self.handle_setting_click(p, s))
            self.settings_box.addWidget(s_btn)

        self.del_btn = QPushButton("delete plugin")
        self.del_btn.setObjectName("ActionBtn")
        self.del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.del_btn.setStyleSheet("color: #ff4444; border-color: rgba(255, 68, 68, 60);")
        self.del_btn.clicked.connect(lambda: self.ktools.remove_plugin(data.get('id')))
        self.settings_box.addWidget(self.del_btn)

        self.plugin_details_scroll.verticalScrollBar().setValue(0)
        
        self.set_main_tab(0)

    def setup_settings_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)

        self.settings_menu_layout = QVBoxLayout()
        self.settings_menu_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.settings_menu_layout.setSpacing(5)

        settings_tabs = ["dependency manager", "about"]
        self.settings_btns = []
        self.settings_group = QButtonGroup(self)
        self.settings_group.setExclusive(True)

        for i, name in enumerate(settings_tabs):
            btn = QPushButton(name)
            btn.setObjectName("SideBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda ch, idx=i: self.settings_stack.setCurrentIndex(idx))
            
            self.settings_btns.append(btn)
            self.settings_group.addButton(btn)
            self.settings_menu_layout.addWidget(btn)

        side_layout.addLayout(self.settings_menu_layout)
        side_layout.addStretch()

        self.settings_stack = QStackedWidget()

        self.tab_deps = QWidget()
        deps_layout = QVBoxLayout(self.tab_deps)
        deps_layout.setContentsMargins(25, 0, 0, 0)
        
        deps_title = QLabel("dependency manager")
        deps_title.setObjectName("PluginTitle")
        
        self.deps_list_scroll = QScrollArea()
        self.deps_list_scroll.setWidgetResizable(True)
        self.deps_list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.deps_list_scroll.setStyleSheet("background: transparent;")
        
        self.deps_list_container = QWidget()
        self.deps_list_vbox = QVBoxLayout(self.deps_list_container)
        self.deps_list_vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.deps_list_scroll.setWidget(self.deps_list_container)
        
        deps_layout.addWidget(deps_title)
        deps_layout.addWidget(self.deps_list_scroll)

        self.tab_about = self._create_settings_info("about", "ktools engine v1.0.0\ndeveloped by kriaiss\ncake is a lie btw\nveksyu s#cks\n\nminimalistic plugin api and manager for macos\n\n>ure on your own with the plugins you're downloading.\nif things go south or your setup starts acting up,\ndon't look at me! its all on you :3")

        self.settings_stack.addWidget(self.tab_deps)
        self.settings_stack.addWidget(self.tab_about)

        layout.addWidget(sidebar)
        layout.addWidget(self.settings_stack)
        
        return page

    def _create_settings_info(self, title, text):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(25, 0, 0, 0)
        t = QLabel(title)
        t.setObjectName("PluginTitle")
        d = QLabel(text)
        d.setObjectName("DetailsText")
        l.addWidget(t)
        l.addWidget(d)
        l.addStretch()
        return w

    def refresh_deps_tab(self):
        while self.deps_list_vbox.count():
            item = self.deps_list_vbox.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        data = self.ktools.dep_mgr._get_data()
        installed_via_ktools = data.get("installed_packages", [])
        system_libs = self.ktools.dep_mgr.ktools_core_libs
        
        if not installed_via_ktools:
            lbl = QLabel("no external packages in inst.json")
            lbl.setObjectName("DetailsText")
            lbl.setStyleSheet("margin-top: 10px; opacity: 0.5;")
            self.deps_list_vbox.addWidget(lbl)
            return

        for pkg in sorted(installed_via_ktools):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 4, 10, 4)
            
            lbl = QLabel(pkg.lower())
            lbl.setObjectName("DetailsText")
            
            row.addWidget(lbl)
            row.addStretch()

            if pkg.lower() not in system_libs:
                del_btn = QPushButton("delete")
                del_btn.setFixedSize(60, 22)
                del_btn.setObjectName("ActionBtn")
                del_btn.setStyleSheet("color: #ff4444; font-size: 10px; border-color: rgba(255,68,68,40);")
                del_btn.clicked.connect(lambda ch, p=pkg: self.uninstall_package(p))
                row.addWidget(del_btn)
            
            self.deps_list_vbox.addWidget(row_widget)

    def uninstall_package(self, pkg_name):
        print(f"dependency manager: manual uninstall: {pkg_name}")
        cmd = self.ktools.dep_mgr.pip_cmd + ["uninstall", "-y", pkg_name]
        subprocess.run(cmd, capture_output=True)
        self.refresh_deps_tab()
        self.ktools.notify(f"removed {pkg_name}")

    def toggle(self):
        if not self.isVisible() or self.windowOpacity() < 0.5:
            self.ktools.request_show("kmanager") 
            
            self.refresh_list()
            self.update_theme()
            self.show()
            self.raise_()

            NSApp.activateIgnoringOtherApps_(True)
            
            self.pos_anim.setStartValue(self.start_pos)
            self.pos_anim.setEndValue(self.end_pos)
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.anim_group.start()
            self.setFocus()
        else:
            self.hide_anim()

    def hide_anim(self):
        if self.is_hiding: return
        self.is_hiding = True
        self.pos_anim.setStartValue(self.end_pos)
        self.pos_anim.setEndValue(self.start_pos)
        self.opacity_anim.setStartValue(1.0)
        self.opacity_anim.setEndValue(0.0)
        self.anim_group.start()
        try: self.anim_group.finished.disconnect()
        except: pass
        self.anim_group.finished.connect(self._finish_hide)

    def _finish_hide(self):
        if self.is_hiding:
            self.hide()
            self.is_hiding = False
            self.ktools.restore_focus()

    def update_theme(self):
        is_dark = NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark"
        self.setStyleSheet(get_theme(is_dark) + self.extra_styles(is_dark))

    def extra_styles(self, is_dark):
        bg = "rgba(30, 30, 30, 240)" if is_dark else "rgba(245, 245, 245, 240)"
        text = "#ffffff" if is_dark else "#000000"
        border = "rgba(255,255,255,15)" if is_dark else "rgba(0,0,0,5)"
        st = "rgba(255,255,255,120)" if is_dark else "rgba(0,0,0,120)"
        btn = "rgba(255,255,255,15)" if is_dark else "rgba(0,0,0,5)"
        
        return f"""
            QWidget#MainContainer {{
                background: {bg};
                border-radius: 24px;
                border: 1px solid {border};
            }}

            QPushButton#ActionBtn {{
                text-align: center; background: {btn}; border: 1px solid {border};
                color: {text}; font-family: 'Menlo'; font-size: 12px; padding: 6px; border-radius: 6px;
            }}
            QPushButton#ActionBtn:hover {{ background: transparent; }}

            QPushButton#BottomNavBtn {{
                background: transparent; border: none; color: {st}; font-family: 'Menlo'; font-size: 13px; padding: 5px 10px;
            }}
            QPushButton#BottomNavBtn:checked {{ color: {text}; border-bottom: 2px solid {text}; }}
            
            QLabel#DetailsText {{ color: {st}; font-family: 'Menlo'; font-size: 13px; }}
        """

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate and self.isVisible() and not self.is_hiding:
            self.hide_anim()
        return super().event(event)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_anim()
        super().keyPressEvent(event)

    def handle_setting_click(self, plugin, setting_name):
        method_name = setting_name.lower().replace(" ", "_")

        if hasattr(plugin, method_name):
            method = getattr(plugin, method_name)
            method()
        else:
            if hasattr(plugin, "on_setting"):
                plugin.on_setting(setting_name)
            else:
                print(f"ktools: plugin dont know what {setting_name} is")

    def add_log(self, message):
        time_str = QTime.currentTime().toString("HH:mm:ss")
        current_text = self.log_display.text()

        lines = (current_text + f"\n[{time_str}] {message}").split('\n')
        self.log_display.setText("\n".join(lines[-100:])) 

        parent_scroll = self.log_display.parent().parent()
        if isinstance(parent_scroll, QScrollArea):
            QTimer.singleShot(10, lambda: parent_scroll.verticalScrollBar().setValue(
                parent_scroll.verticalScrollBar().maximum()
            ))

    def handle_import(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "select plugin zip", "", "Zip files (*.zip)"
        )
        
        if not file_path:
            return

        try:
            plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                top_level_dirs = {name.split('/')[0] for name in zip_ref.namelist() if '/' in name}
                
                if not top_level_dirs:
                    self.ktools.notify("warning: flat zip structure")

                for folder in top_level_dirs:
                    full_path = os.path.join(plugins_dir, folder)
                    if os.path.exists(full_path):
                        print(f"ktools: cleaning up existing plugin: {folder}")
                        shutil.rmtree(full_path)

                zip_ref.extractall(plugins_dir)
                self.ktools.notify(f"imported: {', '.join(top_level_dirs)}")

            QTimer.singleShot(500, self.ktools.reload_all)
            
        except Exception as e:
            self.ktools.notify(f"import error")
            print(f"ktools: import error: {e}")

class DependencyManager:
    def __init__(self, ktools):
        self.ktools = ktools
        self.pip_cmd = self._find_pip()
        self.is_installing = False
        self.ktools_core_libs = {
            "pyqt6", "pyobjc", "pyobjc-core", "pyobjc-framework-appkit", 
            "pyobjc-framework-cocoa", "pyobjc-framework-foundation", "objc", "objgraph"
        }

    def install_missing_manual(self, to_install):
        if self.is_installing or not to_install: return
        self.is_installing = True

        print(f"dependency manager: starting installation of: {to_install}")
        self.ktools.notify(f"installing {len(to_install)} packages...")

        self.worker = InstallWorker(self, to_install)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _get_data(self):
        path = self.ktools._get_inst_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def _find_pip(self):
        bin_dir = os.path.join(sys.prefix, "bin")

        for pip_name in ["pip3", "pip"]:
            pip_path = os.path.join(bin_dir, pip_name)
            if os.path.exists(pip_path):
                return [pip_path]

        for cmd in [sys.executable, 'pip3', 'pip']:
            try:
                if cmd == sys.executable:
                    return [cmd, '-m', 'pip']
                else:
                    subprocess.run([cmd, '--version'], capture_output=True)
                    return [cmd]
            except: continue
        return None

    def get_actually_installed(self):
        if not self.pip_cmd: return set()
        try:
            cmd = self.pip_cmd + ["list", "--format=freeze"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {line.split('==')[0].lower() for line in result.stdout.splitlines()}
        except: return set()

    def install_missing(self):
        if not self.pip_cmd or self.is_installing: return
        
        data = self._get_data()
        actually_installed = self.get_actually_installed()
        to_install = [d.lower() for deps in data.get("plugin_deps", {}).values() 
                      for d in deps if d.lower() not in actually_installed 
                      and d.lower() not in self.ktools_core_libs]

        if not to_install: return

        self.is_installing = True
        self.ktools.notify("installing dependencies...")

        self.worker = InstallWorker(self, list(set(to_install)))
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_finished(self, installed_count):
        self.is_installing = False
        
        if installed_count > 0:
            import importlib
            importlib.invalidate_caches()
            print(f"dependency manager: {installed_count} pkgs installed. reloading plugins...")

            QTimer.singleShot(500, self.ktools.reload_all)
            
            if installed_count < len(self.worker.packages):
                self.ktools.notify("some deps failed, but others installed")
        else:
            print("dependency manager: nothing was installed")
            self.ktools.notify("install failed")

    def cleanup_unused(self):
        if not self.pip_cmd: return
        
        data = self._get_data()
        installed_via_ktools = set(p.lower() for p in data.get("installed_packages", []))

        needed_now = set()
        deps_map = self.ktools.pre_scan_dependencies()
        for deps in deps_map.values():
            for d in deps:
                needed_now.add(d.lower().strip())

        unused = installed_via_ktools - needed_now - self.ktools_core_libs
        
        if unused:
            print(f"dependency manager: physical uninstalling: {unused}")
            cmd = self.pip_cmd + ["uninstall", "-y"] + list(unused)
            subprocess.run(cmd, capture_output=True)

            self.ktools.update_inst_json()

    def is_package_installed(self, pkg_name):
        try:
            importlib.util.find_spec(pkg_name.replace("-", "_"))
            return True
        except:
            return False

    def get_actually_installed(self):
        if not self.pip_cmd: return set()
        try:
            cmd = self.pip_cmd + ["list", "--format=freeze"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {line.split('==')[0].lower() for line in result.stdout.splitlines()}
        except: 
            return set()

class ktools:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.plugins = {}
        self.last_active_app = None
        self.is_switching = False
        self.is_reloading = False
        self.active_toasts = []

        self.dep_mgr = DependencyManager(self) 

        self.manager = PluginManager(self)
        self.setup_tray()

        self.log_emitter = LogEmitter()
        self.log_emitter.sig_log.connect(self.manager.add_log)
        
        sys.stdout = LogStream(self.log_emitter)
        sys.stderr = LogStream(self.log_emitter)

        self.reload_all()
        print("ktools: engine started")

    def pre_scan_dependencies(self):
        plugin_deps_map = {}
        base_path = os.path.dirname(os.path.abspath(__file__))
        p_dir = os.path.join(base_path, "plugins")
        
        if not os.path.exists(p_dir): 
            return {}
        
        for name in os.listdir(p_dir):
            inf_path = os.path.join(p_dir, name, "inf.json")
            if os.path.exists(inf_path):
                try:
                    with open(inf_path, "r", encoding='utf-8') as f:
                        inf = json.load(f)
                        deps = inf.get("dependencies", [])
                        if isinstance(deps, list):
                            clean = [d.strip().lower() for d in deps if d.strip() and d.lower() != "no deps"]
                            plugin_deps_map[name] = clean
                except: continue
        return plugin_deps_map

    def setup_tray(self):
        self.tray = QSystemTrayIcon()
        icon = QIcon(os.path.join(os.path.dirname(__file__), "iconTemplate.png"))
        icon.setIsMask(True)
        self.tray.setIcon(icon)
        self.menu = QMenu()
        self.refresh_menu()
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def refresh_menu(self):
        self.menu.clear()
        act_mgr = QAction("plugin manager", self.menu)
        act_mgr.triggered.connect(self.manager.toggle)
        self.menu.addAction(act_mgr)
        self.menu.addSeparator()
        
        for name, inst in self.plugins.items():
            if hasattr(inst, "get_actions"):
                for act in inst.get_actions(): self.menu.addAction(act)
        
        self.menu.addSeparator()
        act_reload = QAction("reload plugins", self.menu)
        act_reload.triggered.connect(self.reload_all)
        self.menu.addAction(act_reload)
        self.menu.addAction("exit", self.app.quit)

    def load_plugins(self):
        base_path = os.path.dirname(os.path.abspath(__file__))
        p_dir = os.path.join(base_path, "plugins")
        
        if not os.path.exists(p_dir): return

        for name in os.listdir(p_dir):
            path = os.path.join(p_dir, name)
            if os.path.isdir(path):
                py_file = os.path.join(path, f"{name}.py")
                if os.path.exists(py_file):
                    try:
                        self._import_plugin(name, py_file)
                        print(f"ktools: {name} loaded")
                    except Exception as e:
                        print(f"ktools: {name} failed: {e}")

    def _import_plugin(self, name, path):
        try:
            if name in sys.modules:
                del sys.modules[name]
                
            spec = importlib.util.spec_from_file_location(name, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            
            if hasattr(mod, "Plugin"): 
                self.plugins[name] = mod.Plugin(self)
                print(f"ktools: {name} loaded")
        except Exception as e: 
            print(f"ktools: {name} failed: {e}")

    def reload_all(self):
        self.is_reloading = True
        print("\nktools: --- reload start ---")

        for p in list(self.plugins.values()):
            try:
                if hasattr(p, 'unload'): p.unload()
            except: pass
        self.plugins.clear()
        self.load_plugins()

        deps_map = self.pre_scan_dependencies()
        actually_installed = self.dep_mgr.get_actually_installed()
        
        to_install = []
        for p_name, deps in deps_map.items():
            for d in deps:
                d_low = d.lower().strip()
                if d_low not in actually_installed and d_low not in self.dep_mgr.ktools_core_libs:
                    print(f"ktools: missing dependency '{d_low}' for plugin '{p_name}'")
                    to_install.append(d_low)
        
        if to_install:
            self.dep_mgr.install_missing_manual(list(set(to_install)))

        self.update_inst_json(external_deps=deps_map)
        self.refresh_menu()
        if hasattr(self, 'manager'):
            self.manager.refresh_list()
            
        self.is_reloading = False

        gc.collect()
        print(f"ktools: objects in memory: {len(gc.get_objects())}")

        objgraph.show_most_common_types(limit=20)

        print(f"ktools: reload finished. plugins: {len(self.plugins)}")

    def _get_inst_path(self):
        return os.path.join(os.path.dirname(__file__), "inst.json")

    def update_inst_json(self, external_deps=None):
        inst_path = self._get_inst_path()
        plugin_deps_map = external_deps if external_deps is not None else self.pre_scan_dependencies()

        old_data = self.dep_mgr._get_data()
        previously_installed = set(old_data.get("installed_packages", []))
        
        actually_installed = self.dep_mgr.get_actually_installed()

        current_installed = [p for p in previously_installed if p in actually_installed]

        required_now = set()
        for deps in plugin_deps_map.values():
            for d in deps: required_now.add(d.lower())

        final_list = list(set(current_installed) | (required_now & actually_installed))

        data = {
            "installed_packages": sorted(final_list), 
            "plugin_deps": plugin_deps_map,
            "system_scan_time": QDateTime.currentDateTime().toString(Qt.DateFormat.ISODate)
        }

        with open(inst_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def notify(self, text):
        toast = KToast(text, self.active_toasts)

        screen = QApplication.primaryScreen().availableGeometry()
        start_x = (screen.width() - toast.width()) // 2
        toast.move(start_x, screen.height())
        toast.show()

        self.active_toasts.insert(0, toast)
        self.rearrange_toasts()

        QTimer.singleShot(4000, toast.hide_anim)
        toast.destroyed.connect(self.rearrange_toasts)

    def rearrange_toasts(self):
        for i, toast in enumerate(self.active_toasts):
            toast.update_position(i)

    def request_show(self, plugin_name):
        self.is_switching = True
        QTimer.singleShot(600, self._release_switching)
        
        ws = NSWorkspace.sharedWorkspace()
        active = ws.frontmostApplication()
        if active and active.processIdentifier() != os.getpid():
            self.last_active_app = active

        target_win = None
        if plugin_name == "kmanager":
            target_win = self.manager
        else:
            p = self.plugins.get(plugin_name)
            if p:
                target_win = getattr(p, 'shell', getattr(p, 'window', None))

        if target_win:
            self.apply_global_native_flags(target_win)
            NSApp.activateIgnoringOtherApps_(True)

        for name, plugin in self.plugins.items():
            if name == plugin_name: continue
            layer = getattr(plugin, 'layer', 'overlay')
            if layer == 'overlay':
                win = getattr(plugin, 'shell', getattr(plugin, 'window', None))
                if win and win.isVisible():
                    if hasattr(win, 'hide_anim'): win.hide_anim()
                    else: win.hide()
                        
        return True

    def _release_switching(self):
        self.is_switching = False

    def apply_global_native_flags(self, window):
        try:
            ptr = int(window.winId())
            for ns_win in NSApp.windows():
                if abs(ns_win.frame().size.width - window.width()) < 10:

                    behavior = (
                        NSWindowCollectionBehaviorCanJoinAllSpaces | 
                        NSWindowCollectionBehaviorStationary | 
                        NSWindowCollectionBehaviorIgnoresCycle |
                        NSWindowCollectionBehaviorFullScreenAuxiliary
                    )
                    ns_win.setCollectionBehavior_(behavior)

                    ns_win.setLevel_(NSStatusWindowLevel + 1) 
                    ns_win.setHidesOnDeactivate_(False)

                    ns_win.orderFrontRegardless()
                    break
        except Exception as e:
            print(f"ktools: failed to apply native flags: {e}")

    def restore_focus(self):
        if self.is_switching:
            return
            
        if self.last_active_app:
            try:
                ws = NSWorkspace.sharedWorkspace()
                curr_app = ws.frontmostApplication()
                if curr_app and curr_app.processIdentifier() == os.getpid():
                    self.last_active_app.activateWithOptions_(
                        NSApplicationActivateIgnoringOtherApps | 
                        NSApplicationActivateAllWindows
                    )
                    self.last_active_app = None
            except:
                pass

    def reset_switching(self):
        self.is_switching = False

    def get_plugins_info(self):
        info_list = []
        p_dir = os.path.join(os.path.dirname(__file__), "plugins")
        if not os.path.exists(p_dir): return info_list

        for name in os.listdir(p_dir):
            inf_path = os.path.join(p_dir, name, "inf.json")
            if os.path.isfile(inf_path):
                try:
                    with open(inf_path, "r", encoding='utf-8') as f:
                        d = json.load(f)
                        info_list.append({
                            "id": name,
                            "name": d.get("name", name),
                            "author": d.get("author", "unknown"),
                            "version": d.get("version", "1.0.0"),
                            "ktools_v": d.get("ktools_version", "1.0.0"),
                            "desc": d.get("description", "no description"),
                            "deps": d.get("dependencies", []),
                            "settings": d.get("settings", [])
                        })
                except: continue
        return info_list
    
    def remove_plugin(self, plugin_id):
        print(f"ktools: attempting to remove plugin: {plugin_id}")

        if plugin_id in self.plugins:
            try:
                p_inst = self.plugins[plugin_id]
                if hasattr(p_inst, 'unload'):
                    p_inst.unload()
                del self.plugins[plugin_id]
                if plugin_id in sys.modules:
                    del sys.modules[plugin_id]
            except Exception as e:
                print(f"ktools: error unloading before removal: {e}")

        p_dir = os.path.join(os.path.dirname(__file__), "plugins", plugin_id)
        if os.path.exists(p_dir):
            try:
                shutil.rmtree(p_dir)
                print(f"ktools files for {plugin_id} deleted")
            except Exception as e:
                self.notify(f"file error: {e}")
                return

        self.notify(f"plugin {plugin_id} removed")

        self.reload_all()

        QTimer.singleShot(1000, self.dep_mgr.cleanup_unused)

    def run(self): sys.exit(self.app.exec())

if __name__ == "__main__":
    ktools().run()