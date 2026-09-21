import gc
import objgraph
import zipfile
import shutil
import subprocess
import sys
import os
import importlib.util
import json

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class OverlayWindow(QMainWindow):
    def __init__(self, ktools, width=780, height=500):
        super().__init__()
        self.ktools = ktools
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if width and height:
            self.setFixedSize(width, height)
        self.setWindowOpacity(0.0)
        self.is_hiding = False
        self.auto_hide = True
        self.auto_center = True

        self.anim_group = QParallelAnimationGroup(self)
        self.pos_anim = QPropertyAnimation(self, b"pos", self)
        self.opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        
        for a in [self.pos_anim, self.opacity_anim]:
            a.setDuration(150)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.anim_group.addAnimation(a)
            
        self.anim_group.finished.connect(self._on_anim_finished)

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate and self.auto_hide:
            if getattr(self.ktools, 'is_switching', False):
                return super().event(event)
            if self.is_hiding:
                return super().event(event)
            if self.windowOpacity() < 0.95:
                return super().event(event)
            if self.isVisible():
                self.hide_anim()
        return super().event(event)

    def show_anim(self):
        self.is_hiding = False
        if hasattr(self, 'update_system_theme'):
            self.update_system_theme()
        elif hasattr(self, 'update_theme'):
            self.update_theme()
            
        self.show()
        
        start_p = getattr(self, 'start_pos', self.pos())
        end_p = getattr(self, 'end_pos', self.pos())
        self.pos_anim.setStartValue(start_p)
        self.pos_anim.setEndValue(end_p)

        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.anim_group.start()
        
        QTimer.singleShot(500, self._reset_switching)

    def _reset_switching(self):
        if hasattr(self.ktools, 'is_switching'):
            self.ktools.is_switching = False

    def hide_anim(self):
        if self.is_hiding: return
        self.is_hiding = True
        
        start_p = getattr(self, 'start_pos', self.pos())
        end_p = getattr(self, 'end_pos', self.pos())
        self.pos_anim.setStartValue(self.pos())
        self.pos_anim.setEndValue(start_p)
            
        self.opacity_anim.setStartValue(self.windowOpacity())
        self.opacity_anim.setEndValue(0.0)
        self.anim_group.start()

    def _on_anim_finished(self):
        if self.is_hiding:
            self.hide()
            self.setWindowOpacity(0.0)
            self.is_hiding = False
            if hasattr(self.ktools, 'restore_focus'):
                self.ktools.restore_focus()


class FixedWindow(QWidget):
    def __init__(self, ktools):
        super().__init__()
        self.ktools = ktools
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)


class WallpaperWindow(QWidget):
    def __init__(self, ktools):
        super().__init__()
        self.ktools = ktools
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        
    def showEvent(self, event):
        QTimer.singleShot(50, self._apply_desktop_layer)
        super().showEvent(event)

    def _apply_desktop_layer(self):
        try:
            view_ptr = int(self.winId())
            import objc
            ns_view = objc.objc_object(c_void_p=view_ptr)
            window = ns_view.window()
            if window:
                from AppKit import (NSWindowCollectionBehaviorCanJoinAllSpaces, 
                                    NSWindowCollectionBehaviorStationary, 
                                    NSWindowCollectionBehaviorIgnoresCycle)
                behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces | 
                            NSWindowCollectionBehaviorStationary | 
                            NSWindowCollectionBehaviorIgnoresCycle)
                window.setCollectionBehavior_(behavior)
                window.setLevel_(-2147483623)
                window.setHidesOnDeactivate_(False)
                window.setCanHide_(False)
        except Exception as e:
            print(f"ktools API: failed to apply wallpaper layer: {e}")

try:
    from AppKit import (
        NSBundle, NSApplication, NSWorkspace, NSStatusWindowLevel,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary,
        NSWindowCollectionBehaviorIgnoresCycle,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSApplicationActivateIgnoringOtherApps,
        NSApplicationActivateAllWindows,
        NSUserDefaults
    )
    import objc
    
    info = NSBundle.mainBundle().infoDictionary()
    if info:
        info['LSUIElement'] = '1'
except Exception as e:
    print(f"ktools: Failed to load AppKit bindings - {e}")


def apply_liquid_glass(window, radius=24.0):
    try:
        view_ptr = int(window.winId())
        import objc
        ns_view = objc.objc_object(c_void_p=view_ptr)
        ns_win = ns_view.window()
        if ns_win:
            from AppKit import (
                NSViewWidthSizable,
                NSViewHeightSizable,
                NSWindowBelow,
                NSColor
            )
            
            try:
                from AppKit import NSGlassEffectView
                effect_class = NSGlassEffectView
                is_legacy = False
            except ImportError:
                from AppKit import NSVisualEffectView, NSVisualEffectBlendingModeBehindWindow, NSVisualEffectStateActive
                effect_class = NSVisualEffectView
                is_legacy = True

            ns_win.setOpaque_(False)
            ns_win.setBackgroundColor_(NSColor.clearColor())
            
            qt_view = ns_win.contentView()
            theme_frame = qt_view.superview()
            
            for subview in theme_frame.subviews():
                if subview.className() in ['NSGlassEffectView', 'NSVisualEffectView']:
                    return
                    
            effect_view = effect_class.alloc().initWithFrame_(qt_view.frame())
            effect_view.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
            
            if is_legacy:
                effect_view.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
                effect_view.setMaterial_(13)
                effect_view.setState_(NSVisualEffectStateActive)
            
            effect_view.setWantsLayer_(True)
            effect_view.layer().setCornerRadius_(radius)
            effect_view.layer().setMasksToBounds_(True)
            
            theme_frame.addSubview_positioned_relativeTo_(effect_view, NSWindowBelow, qt_view)
    except Exception as e:
        print(f"ktools: failed to apply liquid glass: {e}")

def get_theme(is_dark):
    bg = "transparent"
    text = "#ffffff" if is_dark else "#000000"
    nav_text = "rgba(255, 255, 255, 120)" if is_dark else "rgba(0, 0, 0, 120)"
    border = "rgba(255, 255, 255, 30)" if is_dark else "rgba(0, 0, 0, 30)"
    item_hover = "rgba(255, 255, 255, 20)" if is_dark else "rgba(0, 0, 0, 10)"
    scroll_handle = "rgba(255, 255, 255, 40)" if is_dark else "rgba(0, 0, 0, 40)"
    scroll_hover = "rgba(255, 255, 255, 70)" if is_dark else "rgba(0, 0, 0, 70)"
    menu_bg = "transparent"
    
    return f"""
    QMenu {{
        background-color: {menu_bg};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 5px;
        font-family: 'Menlo';
    }}
    QMenu::item {{
        padding: 6px 25px 6px 20px;
        background-color: transparent;
        color: {text};
        border-radius: 4px;
        font-family: 'Menlo';
    }}
    QMenu::item:selected {{
        background-color: {item_hover};
    }}
    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 4px 10px;
    }}
    QPushButton#PluginTabBtn {{
        color: {nav_text}; background: transparent; border: none;
        font-family: 'Menlo'; font-size: 14px; padding: 8px 12px;
        border-bottom: 2px solid transparent; margin: 0px 2px;
    }}
    QPushButton#PluginTabBtn:checked {{ color: {text}; border-bottom: 2px solid {text}; }}
    
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
        border: none; background: transparent; width: 8px; margin: 0px 2px 0px 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {scroll_handle}; border-radius: 4px; min-height: 40px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {scroll_hover};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px; background: none;
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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setFixedSize(400, 40)
        
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
        primary = QApplication.primaryScreen()
        if primary:
            screen = primary.availableGeometry()
            target_y = screen.height() - 80 - (index * 55)
            target_x = (screen.width() - self.width()) // 2
        else:
            target_y = 1080 - 80 - (index * 55)
            target_x = (1920 - self.width()) // 2
        
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
        try:
            if self in self.manager_list:
                self.manager_list.remove(self)
        except ValueError:
            pass
        super().closeEvent(event)

    def update_theme(self):
        defaults = NSUserDefaults.standardUserDefaults()
        is_dark = defaults.stringForKey_("AppleInterfaceStyle") == "Dark" if defaults else True
        
        bg = "transparent"
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
            view_ptr = int(self.winId())
            ns_view = objc.objc_object(c_void_p=view_ptr)
            window = ns_view.window()
            if window:
                window.setLevel_(NSStatusWindowLevel + 1)
                window.setHidesOnDeactivate_(False)
                behavior = (NSWindowCollectionBehaviorCanJoinAllSpaces | 
                            NSWindowCollectionBehaviorStationary | 
                            NSWindowCollectionBehaviorIgnoresCycle)
                window.setCollectionBehavior_(behavior)
                
            apply_liquid_glass(self, radius=20.0)
        except Exception: 
            pass


class LogEmitter(QObject):
    sig_log = pyqtSignal(str)


class LogStream:
    def __init__(self, emitter, original_stream):
        self.emitter = emitter
        self.original_stream = original_stream

    def write(self, text):
        if text.strip():
            self.emitter.sig_log.emit(text.strip())
        self.original_stream.write(text)

    def flush(self):
        self.original_stream.flush()


class InstallWorker(QThread):
    finished = pyqtSignal(list)
    
    def __init__(self, dep_mgr, packages):
        super().__init__()
        self.dep_mgr = dep_mgr
        self.packages = packages

    def run(self):
        installed_pkgs = []
        for pkg in self.packages:
            print(f"dependency manager: installing: {pkg}")
            cmd = self.dep_mgr.pip_cmd + ["install", pkg]
            
            if sys.prefix == sys.base_prefix:
                cmd.extend(["--user", "--break-system-packages"])

            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                installed_pkgs.append(pkg)
            else:
                print(f"dependency manager: failed to install {pkg}: {res.stderr}")
        
        self.finished.emit(installed_pkgs)


class PluginCard(QPushButton):
    def __init__(self, name, is_active=False):
        super().__init__(name.lower())
        self.setObjectName("PluginTabBtn")
        self.setCheckable(True)
        self.setChecked(is_active)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class PluginManager(OverlayWindow):
    def __init__(self, ktools_instance):
        super().__init__(ktools_instance, width=780, height=500)
        self.auto_hide = False

        self.root = QWidget()
        self.root.setObjectName("MainContainer")

        self.outer_vbox = QVBoxLayout(self.root)
        self.outer_vbox.setContentsMargins(10, 10, 10, 15)

        self.content_area = QStackedWidget()

        self.plugins_page = QWidget()
        plugins_layout = QVBoxLayout(self.plugins_page)
        plugins_layout.setContentsMargins(0, 0, 0, 0)
        plugins_layout.setSpacing(15)

        self.plugin_nav_scroll = QScrollArea()
        self.plugin_nav_scroll.setFixedHeight(45)
        self.plugin_nav_scroll.setWidgetResizable(True)
        self.plugin_nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.plugin_nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plugin_nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plugin_nav_scroll.setStyleSheet("background: transparent;")
        self.plugin_nav_scroll.wheelEvent = self.plugin_nav_wheel_event

        self.plugin_nav_container = QWidget()
        self.plugin_list_layout = QHBoxLayout(self.plugin_nav_container)
        self.plugin_list_layout.setContentsMargins(10, 0, 10, 0)
        self.plugin_list_layout.setSpacing(5)
        self.plugin_list_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.plugin_nav_scroll.setWidget(self.plugin_nav_container)

        self.plugin_details_scroll = QScrollArea()
        self.plugin_details_scroll.setWidgetResizable(True)
        self.plugin_details_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.plugin_details_scroll.setStyleSheet("background: transparent;")

        self.plugin_details_stack = QStackedWidget()
        self.info_views = []
        
        for _ in range(2):
            view = QWidget()
            view.setObjectName("PluginDetailsWidget")
            info_layout = QVBoxLayout(view)
            info_layout.setContentsMargins(10, 0, 15, 0) 
            info_layout.setSpacing(15)
            info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

            title = QLabel("select a plugin")
            title.setObjectName("PluginTitle")
            details = QLabel("")
            details.setWordWrap(True)
            details.setObjectName("DetailsText")
            details.setAlignment(Qt.AlignmentFlag.AlignTop)

            info_layout.addWidget(title)
            info_layout.addWidget(details)
            
            settings_box = QVBoxLayout() 
            settings_box.setSpacing(10)
            settings_box.setAlignment(Qt.AlignmentFlag.AlignTop)
            info_layout.addLayout(settings_box)
            info_layout.addStretch()
            
            self.plugin_details_stack.addWidget(view)
            self.info_views.append({
                'view': view,
                'title': title,
                'details': details,
                'settings_box': settings_box
            })

        self.plugin_details_scroll.setWidget(self.plugin_details_stack)

        plugins_layout.addWidget(self.plugin_nav_scroll)
        plugins_layout.addWidget(self.plugin_details_scroll)

        self.content_area.addWidget(self.plugins_page)

        self.settings_page = self.setup_settings_page()
        self.content_area.addWidget(self.settings_page)

        self.log_view = QWidget()
        log_layout = QVBoxLayout(self.log_view)
        log_layout.setContentsMargins(10, 0, 0, 0)
        
        self.log_display = QLabel("")
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

        self.nav_btns = []
        for i, name in enumerate(["plugins manager", "ktools settings", "logs"]):
            btn = QPushButton(name)
            btn.setObjectName("BottomNavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda ch, idx=i: self.set_main_tab(idx))
            self.nav_btns.append(btn)

        self.main_nav_scroll = QScrollArea()
        self.main_nav_scroll.setFixedHeight(45)
        self.main_nav_scroll.setWidgetResizable(True)
        self.main_nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.main_nav_scroll.setStyleSheet("background: transparent;")
        self.main_nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.main_nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.main_nav_scroll.wheelEvent = self.main_nav_wheel_event
        
        self.main_nav_container = QWidget()
        self.main_nav_layout = QHBoxLayout(self.main_nav_container)
        self.main_nav_layout.setContentsMargins(10, 0, 10, 0)
        self.main_nav_layout.setSpacing(5)
        self.main_nav_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.main_nav_scroll.setWidget(self.main_nav_container)
        
        for btn in self.nav_btns: 
            self.main_nav_layout.addWidget(btn)

        self.nav_hbox = QHBoxLayout()
        self.nav_hbox.setContentsMargins(0, 0, 0, 0)
        self.nav_hbox.addWidget(self.main_nav_scroll)
        self.nav_hbox.addStretch()

        self.reload_btn = QPushButton("reload plugins")
        self.reload_btn.setObjectName("ActionBtn")
        self.reload_btn.clicked.connect(lambda checked=False: self.ktools.reload_all())

        self.import_btn = QPushButton("import plugins")
        self.import_btn.setObjectName("ActionBtn")
        self.import_btn.clicked.connect(self.handle_import)

        self.nav_hbox.addWidget(self.import_btn)
        self.nav_hbox.addWidget(self.reload_btn)

        self.outer_vbox.addWidget(self.content_area)
        self.outer_vbox.addLayout(self.nav_hbox)

        self.setCentralWidget(self.root)


        self.plugin_group = QButtonGroup(self)
        self.plugin_group.setExclusive(True)
        
        self.is_hiding = False
        self.installEventFilter(self)
        self.update_theme()

    def plugin_nav_wheel_event(self, event):
        delta = event.angleDelta()
        if abs(delta.x()) > abs(delta.y()):
            val = self.plugin_nav_scroll.horizontalScrollBar().value() - delta.x()
        else:
            val = self.plugin_nav_scroll.horizontalScrollBar().value() - delta.y()
        self.plugin_nav_scroll.horizontalScrollBar().setValue(val)

    def main_nav_wheel_event(self, event):
        delta = event.angleDelta()
        if abs(delta.x()) > abs(delta.y()):
            val = self.main_nav_scroll.horizontalScrollBar().value() - delta.x()
        else:
            val = self.main_nav_scroll.horizontalScrollBar().value() - delta.y()
        self.main_nav_scroll.horizontalScrollBar().setValue(val)

    def settings_nav_wheel_event(self, event):
        delta = event.angleDelta()
        if abs(delta.x()) > abs(delta.y()):
            val = self.settings_nav_scroll.horizontalScrollBar().value() - delta.x()
        else:
            val = self.settings_nav_scroll.horizontalScrollBar().value() - delta.y()
        self.settings_nav_scroll.horizontalScrollBar().setValue(val)

    def set_main_tab(self, idx):
        if idx < 0 or idx >= self.content_area.count():
            return
            
        old_idx = self.content_area.currentIndex()
        
        if old_idx != idx:
            direction = 1 if old_idx == -1 or idx > old_idx else -1
            
            if old_idx != -1:
                old_widget = self.content_area.widget(old_idx)
                new_widget = self.content_area.widget(idx)
                
                if hasattr(self, 'slide_group') and self.slide_group.state() == QParallelAnimationGroup.State.Running:
                    self.slide_group.stop()
                    
                for i in range(self.content_area.count()):
                    if i != old_idx and i != idx:
                        w = self.content_area.widget(i)
                        w.hide()
                        w.move(0, 0)
                
                self.content_area.setCurrentIndex(idx)
                
                old_widget.setGeometry(self.content_area.rect())
                old_widget.show()
                old_widget.raise_()
                new_widget.raise_()
                
                start_x = direction * (self.content_area.width() or 780)
                
                self.slide_group = QParallelAnimationGroup(self)
                
                anim_in = QPropertyAnimation(new_widget, b"pos")
                anim_in.setDuration(250)
                anim_in.setStartValue(QPoint(start_x, 0))
                anim_in.setEndValue(QPoint(0, 0))
                anim_in.setEasingCurve(QEasingCurve.Type.OutQuart)
                
                anim_out = QPropertyAnimation(old_widget, b"pos")
                anim_out.setDuration(250)
                anim_out.setStartValue(QPoint(0, 0))
                anim_out.setEndValue(QPoint(-start_x, 0))
                anim_out.setEasingCurve(QEasingCurve.Type.OutQuart)
                
                self.slide_group.addAnimation(anim_in)
                self.slide_group.addAnimation(anim_out)
                
                def finish_anim(w_old=old_widget):
                    w_old.hide()
                    w_old.move(0, 0)
                    
                self.slide_group.finished.connect(finish_anim)
                self.slide_group.start()
            else:
                self.content_area.setCurrentIndex(idx)
                
        for i, b in enumerate(self.nav_btns):
            b.setChecked(i == idx)

        if idx == 1:
            self.refresh_deps_tab()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def refresh_list(self):
        self._clear_layout(self.plugin_list_layout)
        plugins = self.ktools.get_plugins_info()

        for i, data in enumerate(plugins):
            btn = PluginCard(data.get('name', 'unknown'), is_active=(i==0))
            self.plugin_group.addButton(btn)
            btn.clicked.connect(lambda checked, d=data, b=btn: self.show_plugin_details(d, b))
            self.plugin_list_layout.addWidget(btn)
        
        if plugins: 
            first_btn = self.plugin_list_layout.itemAt(0).widget()
            self.show_plugin_details(plugins[0], first_btn)

    def show_plugin_details(self, data, active_btn=None):
        if active_btn:
            self.plugin_nav_scroll.ensureWidgetVisible(active_btn, 50, 0)
            
            target_layout_idx = -1
            for i in range(self.plugin_list_layout.count()):
                item = self.plugin_list_layout.itemAt(i)
                if item and item.widget() == active_btn:
                    target_layout_idx = i
                    break
                    
            current_layout_idx = getattr(self, 'current_plugin_layout_idx', -1)
            
            if target_layout_idx != -1:
                direction = 1 if current_layout_idx == -1 or target_layout_idx > current_layout_idx else -1
                self.current_plugin_layout_idx = target_layout_idx
            else:
                direction = 1
                
            for b in self.plugin_group.buttons():
                b.setChecked(b == active_btn)
        else:
            direction = 1

        old_idx = self.plugin_details_stack.currentIndex()
        new_idx = 1 if old_idx == 0 else 0
        
        target = self.info_views[new_idx]

        target['title'].setText(data.get('name', 'unknown').lower())
        
        details = (
            f"author: {data.get('author', 'kriaiss')}\n"
            f"version: {data.get('version', '1.0.0')}\n"
            f"dependencies: {', '.join(data.get('deps', []))}\n\n"
            f"description:\n{data.get('desc', 'no description')}\n"
        )
        target['details'].setText(details)

        plugin_instance = self.ktools.plugins.get(data.get('id'))
        self._clear_layout(target['settings_box'])

        for setting_name in data.get('settings', []):
            s_btn = QPushButton(setting_name.lower())
            s_btn.setObjectName("ActionBtn")
            s_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            if plugin_instance:
                s_btn.clicked.connect(lambda checked, s=setting_name, p=plugin_instance: 
                                      self.handle_setting_click(p, s))
            target['settings_box'].addWidget(s_btn)

        if plugin_instance and hasattr(plugin_instance, 'config_path') and os.path.exists(plugin_instance.config_path):
            cfg_btn = QPushButton("open config.json")
            cfg_btn.setObjectName("ActionBtn")
            cfg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cfg_btn.setStyleSheet("color: #729fcf; border-color: rgba(114, 159, 207, 40);")
            cfg_btn.clicked.connect(lambda checked, p=plugin_instance.config_path: subprocess.Popen(["open", "-t", p]))
            target['settings_box'].addWidget(cfg_btn)

        del_btn = QPushButton("delete plugin")
        del_btn.setObjectName("ActionBtn")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("color: #ff4444; border-color: rgba(255, 68, 68, 60);")
        del_btn.clicked.connect(lambda: self.ktools.remove_plugin(data.get('id')))
        target['settings_box'].addWidget(del_btn)

        if old_idx != -1:
            old_widget = self.plugin_details_stack.widget(old_idx)
            new_widget = self.plugin_details_stack.widget(new_idx)
            
            if hasattr(self, 'details_slide_group') and self.details_slide_group.state() == QParallelAnimationGroup.State.Running:
                self.details_slide_group.stop()
                
            for i in range(self.plugin_details_stack.count()):
                if i != old_idx and i != new_idx:
                    w = self.plugin_details_stack.widget(i)
                    w.hide()
                    w.move(0, 0)
            
            self.plugin_details_stack.setCurrentIndex(new_idx)
            
            old_widget.setGeometry(self.plugin_details_stack.rect())
            old_widget.show()
            old_widget.raise_()
            new_widget.raise_()
            
            start_x = direction * (self.plugin_details_scroll.width() or 400)
            
            self.details_slide_group = QParallelAnimationGroup(self)
            
            anim_in = QPropertyAnimation(new_widget, b"pos")
            anim_in.setDuration(250)
            anim_in.setStartValue(QPoint(start_x, 0))
            anim_in.setEndValue(QPoint(0, 0))
            anim_in.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            anim_out = QPropertyAnimation(old_widget, b"pos")
            anim_out.setDuration(250)
            anim_out.setStartValue(QPoint(0, 0))
            anim_out.setEndValue(QPoint(-start_x, 0))
            anim_out.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            self.details_slide_group.addAnimation(anim_in)
            self.details_slide_group.addAnimation(anim_out)
            
            def finish_anim(w_old=old_widget):
                w_old.hide()
                w_old.move(0, 0)
                
            self.details_slide_group.finished.connect(finish_anim)
            self.details_slide_group.start()
        else:
            self.plugin_details_stack.setCurrentIndex(new_idx)

        self.plugin_details_scroll.verticalScrollBar().setValue(0)
        self.set_main_tab(0)

    def setup_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        self.settings_nav_scroll = QScrollArea()
        self.settings_nav_scroll.setFixedHeight(45)
        self.settings_nav_scroll.setWidgetResizable(True)
        self.settings_nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.settings_nav_scroll.setStyleSheet("background: transparent;")
        self.settings_nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_nav_scroll.wheelEvent = self.settings_nav_wheel_event

        self.settings_nav_container = QWidget()
        self.settings_menu_layout = QHBoxLayout(self.settings_nav_container)
        self.settings_menu_layout.setContentsMargins(10, 0, 10, 0)
        self.settings_menu_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.settings_menu_layout.setSpacing(5)
        
        self.settings_nav_scroll.setWidget(self.settings_nav_container)

        settings_tabs = ["dependency manager", "about"]
        self.settings_btns = []
        self.settings_group = QButtonGroup(self)
        self.settings_group.setExclusive(True)

        for i, name in enumerate(settings_tabs):
            btn = QPushButton(name)
            btn.setObjectName("PluginTabBtn")
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda ch, idx=i: self.set_settings_tab(idx))
            
            self.settings_btns.append(btn)
            self.settings_group.addButton(btn)
            self.settings_menu_layout.addWidget(btn)

        self.settings_stack = QStackedWidget()

        self.tab_deps = QWidget()
        deps_layout = QVBoxLayout(self.tab_deps)
        deps_layout.setContentsMargins(10, 0, 0, 0)
        
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

        self.tab_about = self._create_settings_info("about", "ktools engine v1.0.1\ndeveloped by kriaiss\ncake is a lie\n\nminimalistic plugin api and manager for macos\n\n>you are entirely on your own with the third-party plugins you download or create.\nif a poorly written script hangs your system or your setup starts acting up,\ndon't look at me! it's all on you. :3")

        self.settings_stack.addWidget(self.tab_deps)
        self.settings_stack.addWidget(self.tab_about)

        layout.addWidget(self.settings_nav_scroll)
        layout.addWidget(self.settings_stack)
        
        return page

    def set_settings_tab(self, idx):
        if idx < 0 or idx >= self.settings_stack.count():
            return
            
        old_idx = self.settings_stack.currentIndex()
        
        if old_idx != idx:
            direction = 1 if old_idx == -1 or idx > old_idx else -1
            
            if old_idx != -1:
                old_widget = self.settings_stack.widget(old_idx)
                new_widget = self.settings_stack.widget(idx)
                
                if hasattr(self, 'settings_slide_group') and self.settings_slide_group.state() == QParallelAnimationGroup.State.Running:
                    self.settings_slide_group.stop()
                    
                for i in range(self.settings_stack.count()):
                    if i != old_idx and i != idx:
                        w = self.settings_stack.widget(i)
                        w.hide()
                        w.move(0, 0)
                
                self.settings_stack.setCurrentIndex(idx)
                
                old_widget.setGeometry(self.settings_stack.rect())
                old_widget.show()
                old_widget.raise_()
                new_widget.raise_()
                
                start_x = direction * (self.settings_stack.width() or 780)
                
                self.settings_slide_group = QParallelAnimationGroup(self)
                
                anim_in = QPropertyAnimation(new_widget, b"pos")
                anim_in.setDuration(250)
                anim_in.setStartValue(QPoint(start_x, 0))
                anim_in.setEndValue(QPoint(0, 0))
                anim_in.setEasingCurve(QEasingCurve.Type.OutQuart)
                
                anim_out = QPropertyAnimation(old_widget, b"pos")
                anim_out.setDuration(250)
                anim_out.setStartValue(QPoint(0, 0))
                anim_out.setEndValue(QPoint(-start_x, 0))
                anim_out.setEasingCurve(QEasingCurve.Type.OutQuart)
                
                self.settings_slide_group.addAnimation(anim_in)
                self.settings_slide_group.addAnimation(anim_out)
                
                def finish_anim(w_old=old_widget):
                    w_old.hide()
                    w_old.move(0, 0)
                    
                self.settings_slide_group.finished.connect(finish_anim)
                self.settings_slide_group.start()
            else:
                self.settings_stack.setCurrentIndex(idx)
                
        for i, b in enumerate(self.settings_btns):
            b.setChecked(i == idx)
    def _create_settings_info(self, title, text):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(10, 0, 0, 0)
        t = QLabel(title)
        t.setObjectName("PluginTitle")
        d = QLabel(text)
        d.setObjectName("DetailsText")
        l.addWidget(t)
        l.addWidget(d)
        l.addStretch()
        return w

    def refresh_deps_tab(self):
        self._clear_layout(self.deps_list_vbox)

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
        self.ktools.toggle_plugin("kmanager")

    def update_theme(self):
        defaults = NSUserDefaults.standardUserDefaults()
        is_dark = defaults.stringForKey_("AppleInterfaceStyle") == "Dark" if defaults else True
        self.setStyleSheet(get_theme(is_dark) + self.extra_styles(is_dark))

    def extra_styles(self, is_dark):
        bg = "transparent"
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
            plugins_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "plugins"))
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for member in zip_ref.namelist():
                    extracted_path = os.path.abspath(os.path.join(plugins_dir, member))
                    if not extracted_path.startswith(plugins_dir):
                        raise SecurityError("Attempted Path Traversal in Zip File")
                
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
            self.ktools.notify("import error")
            print(f"ktools: import error: {e}")


class DependencyManager:
    def __init__(self, ktools_instance):
        self.ktools = ktools_instance
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
            except Exception: pass
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
            except Exception: continue
        return None

    def is_package_installed(self, pkg_name):
        import importlib.metadata
        try:
            importlib.metadata.version(pkg_name)
            return True
        except importlib.metadata.PackageNotFoundError:
            return False

    def install_missing(self):
        if not self.pip_cmd or self.is_installing: return
        
        data = self._get_data()
        installed_via_ktools = set(data.get("installed_packages", []))
        to_install = []
        for deps in data.get("plugin_deps", {}).values():
            for d in deps:
                d_low = d.lower()
                if d_low not in self.ktools_core_libs and d_low not in installed_via_ktools and not self.is_package_installed(d_low):
                    to_install.append(d_low)

        to_install = list(set(to_install))

        if not to_install: return

        self.is_installing = True
        self.ktools.notify("installing dependencies...")

        self.worker = InstallWorker(self, to_install)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_install_finished(self, installed_pkgs):
        self.is_installing = False
        
        if installed_pkgs:
            data = self._get_data()
            current_installed = set(data.get("installed_packages", []))
            for pkg in installed_pkgs:
                current_installed.add(pkg.lower())
            
            data["installed_packages"] = sorted(list(current_installed))
            with open(self.ktools._get_inst_path(), "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            import importlib
            importlib.invalidate_caches()
            print(f"dependency manager: {len(installed_pkgs)} pkgs installed. reloading plugins...")

            QTimer.singleShot(500, self.ktools.reload_all)
            
            if len(installed_pkgs) < len(self.worker.packages):
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
            res = subprocess.run(cmd, capture_output=True)
            
            if res.returncode == 0:
                data["installed_packages"] = sorted(list(installed_via_ktools - unused))
                with open(self.ktools._get_inst_path(), "w", encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)


class ktools:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        def custom_excepthook(exc_type, exc_value, exc_traceback):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            import traceback
            tb = traceback.extract_tb(exc_traceback)
            plugins_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugins")
            culprit = None
            for frame in tb:
                if frame.filename.startswith(plugins_path):
                    rel = os.path.relpath(frame.filename, plugins_path)
                    parts = rel.split(os.sep)
                    if parts:
                        culprit = parts[0]
                        break
            if culprit and hasattr(self, 'plugins') and culprit in self.plugins:
                err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                QTimer.singleShot(0, lambda: self.isolate_plugin_crash(culprit, err_msg))

        sys.excepthook = custom_excepthook
        
        try:
            import AppKit
            AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        except Exception: pass
        self.plugins = {}
        self.last_active_app = None
        self.is_switching = False
        self.is_reloading = False
        self.active_toasts = []

        self.dep_mgr = DependencyManager(self) 

        self.manager = PluginManager(self)
        self.apply_global_native_flags(self.manager, is_overlay=True)
        self.setup_tray()

        self.log_emitter = LogEmitter()
        self.log_emitter.sig_log.connect(self.manager.add_log)
        
        sys.stdout = LogStream(self.log_emitter, sys.stdout)
        sys.stderr = LogStream(self.log_emitter, sys.stderr)
        
        QTimer.singleShot(500, self.manager.toggle)

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
                except Exception: continue
        return plugin_deps_map

    # i love mac os 27 :) another crash fix
    def setup_tray(self):
        self.tray = QSystemTrayIcon()
        icon = QIcon(os.path.join(os.path.dirname(__file__), "iconTemplate.png"))
        icon.setIsMask(True)
        self.tray.setIcon(icon)
        self.menu = QMenu()

        self.menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.menu.setWindowFlags(self.menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)

        defaults = NSUserDefaults.standardUserDefaults()
        is_dark = defaults.stringForKey_("AppleInterfaceStyle") == "Dark" if defaults else True
        self.menu.setStyleSheet(get_theme(is_dark))

        self.refresh_menu()
        
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            apply_liquid_glass(self.menu, radius=8.0)
            self.refresh_menu()
            self.menu.popup(QCursor.pos())

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
        
        act_exit = QAction("exit", self.menu)
        act_exit.triggered.connect(self.app.quit)
        self.menu.addAction(act_exit)

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
                plugin_instance = mod.Plugin(self)
                self.plugins[name] = plugin_instance
                target_win = getattr(plugin_instance, 'shell', getattr(plugin_instance, 'window', getattr(plugin_instance, 'monitor', None)))
                target_layer = getattr(plugin_instance, 'layer', 'overlay')
                if target_win:
                    self.apply_global_native_flags(target_win, is_overlay=(target_layer == 'overlay'))
        except Exception as e: 
            print(f"ktools: {name} failed to import: {e}")

    def reload_all(self):
        self.is_reloading = True
        print("\nktools: --- reload start ---")

        for p in list(self.plugins.values()):
            try:
                if hasattr(p, 'unload'): p.unload()
            except Exception: pass
        self.plugins.clear()
        self.load_plugins()

        deps_map = self.pre_scan_dependencies()
        
        installed_via_ktools = set(self.dep_mgr._get_data().get("installed_packages", []))
        to_install = []
        for p_name, deps in deps_map.items():
            for d in deps:
                d_low = d.lower().strip()
                if d_low not in self.dep_mgr.ktools_core_libs and d_low not in installed_via_ktools and not self.dep_mgr.is_package_installed(d_low):
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

        try:
            objgraph.show_most_common_types(limit=20)
        except Exception:
            pass

        print(f"ktools: reload finished. plugins: {len(self.plugins)}")
        self.notify("plugins reloaded")

    def _get_inst_path(self):
        return os.path.join(os.path.dirname(__file__), "inst.json")

    def update_inst_json(self, external_deps=None):
        inst_path = self._get_inst_path()
        plugin_deps_map = external_deps if external_deps is not None else self.pre_scan_dependencies()

        old_data = self.dep_mgr._get_data()
        previously_installed = set(old_data.get("installed_packages", []))
        
        data = {
            "installed_packages": sorted(list(previously_installed)), 
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

        QTimer.singleShot(10, toast._apply_native_flags)
        
        self.rearrange_toasts()
        QTimer.singleShot(4000, toast.hide_anim)
        toast.destroyed.connect(self.rearrange_toasts)

    def rearrange_toasts(self):
        for i, toast in enumerate(self.active_toasts):
            try:
                toast.update_position(i)
            except RuntimeError:
                pass

    def toggle_plugin(self, plugin_name):
        target_win = None
        target_layer = 'overlay'
        
        if plugin_name == "kmanager":
            target_win = self.manager
            target_layer = 'overlay'
        else:
            p = self.plugins.get(plugin_name)
            if p:
                target_win = getattr(p, 'shell', getattr(p, 'window', getattr(p, 'monitor', None)))
                target_layer = getattr(p, 'layer', 'overlay')

        if not target_win:
            return
            
        if hasattr(target_win, 'anim_group') and target_win.anim_group.state() == QParallelAnimationGroup.State.Running:
            return

        is_visible = target_win.isVisible()
        if hasattr(target_win, 'windowOpacity'):
            is_visible = is_visible and target_win.windowOpacity() > 0.1

        if is_visible:
            if hasattr(target_win, 'hide_anim'): target_win.hide_anim()
            else: target_win.hide()
        else:
            self.is_switching = True
            QTimer.singleShot(600, self._release_switching)
            
            try:
                ws = NSWorkspace.sharedWorkspace()
                active = ws.frontmostApplication()
                if active and active.processIdentifier() != os.getpid():
                    self.last_active_app = active
            except Exception:
                pass
                
            closed_other = False
            if target_layer == 'overlay':
                for name, plugin in self.plugins.items():
                    if name == plugin_name: continue
                    layer = getattr(plugin, 'layer', 'overlay')
                    if layer == 'overlay':
                        win = getattr(plugin, 'shell', getattr(plugin, 'window', getattr(plugin, 'monitor', None)))
                        if win and win.isVisible():
                            if hasattr(win, 'hide_anim'): win.hide_anim()
                            else: win.hide()
                            closed_other = True
                            
                if plugin_name != "kmanager" and self.manager.isVisible():
                    self.manager.hide()
                    closed_other = True

            delay = 120 if closed_other else 0
            is_ov = (target_layer == 'overlay')
            QTimer.singleShot(delay, lambda: self._execute_show(target_win, is_overlay=is_ov))

    def _execute_show(self, target_win, is_overlay=True):
        if is_overlay:
            try:
                screen = QGuiApplication.screenAt(QCursor.pos())
                if not screen:
                    screen = QApplication.primaryScreen()
                screen_geo = screen.availableGeometry()
                
                if getattr(target_win, 'auto_center', True):
                    target_x = screen_geo.center().x() - int(target_win.width() / 2)
                    target_y = screen_geo.center().y() - int(target_win.height() / 2)

                    y_offset = -40
                    if hasattr(target_win, 'start_pos') and hasattr(target_win, 'end_pos'):
                        y_offset = target_win.start_pos.y() - target_win.end_pos.y()
                    
                    target_win.end_pos = QPoint(target_x, target_y)
                    target_win.start_pos = QPoint(target_x, target_y + y_offset)
                    target_win.move(target_win.start_pos)
            except Exception as e:
                print(f"ktools: failed to auto-center overlay: {e}")

        if hasattr(target_win, 'show_anim'):
            target_win.show_anim()
        else:
            target_win.show()
            
        target_win.raise_()
        target_win.activateWindow()
            
        try:
            self.apply_global_native_flags(target_win, is_overlay=is_overlay)
        except Exception: pass

    def _release_switching(self):
        self.is_switching = False

    def apply_global_native_flags(self, window, retries=10, is_overlay=False):
        try:
            view_ptr = int(window.winId())
            import objc
            ns_view = objc.objc_object(c_void_p=view_ptr)
            ns_win = ns_view.window()
            if ns_win:
                from AppKit import (
                    NSWindowCollectionBehaviorCanJoinAllSpaces,
                    NSWindowCollectionBehaviorMoveToActiveSpace,
                    NSWindowCollectionBehaviorStationary,
                    NSWindowCollectionBehaviorIgnoresCycle,
                    NSWindowCollectionBehaviorFullScreenAuxiliary,
                    NSStatusWindowLevel
                )
                behavior = (
                    NSWindowCollectionBehaviorStationary | 
                    NSWindowCollectionBehaviorIgnoresCycle |
                    NSWindowCollectionBehaviorFullScreenAuxiliary
                )
                if is_overlay:
                    behavior |= NSWindowCollectionBehaviorMoveToActiveSpace
                else:
                    behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
                    
                ns_win.setCollectionBehavior_(behavior)
                ns_win.setLevel_(NSStatusWindowLevel + 1) 
                ns_win.setHidesOnDeactivate_(False)
                ns_win.makeKeyAndOrderFront_(None)
                
                apply_liquid_glass(window, radius=24.0)
            else:
                if retries > 0:
                    QTimer.singleShot(20, lambda: self.apply_global_native_flags(window, retries - 1, is_overlay))
        except Exception as e:
            print(f"ktools: failed to apply native flags: {e}")

    def _app_has_windows_on_current_space(self, pid):
        try:
            import Quartz
            options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
            window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)
            for window in window_list:
                if window.get(Quartz.kCGWindowOwnerPID) == pid:
                    if window.get(Quartz.kCGWindowLayer, 0) == 0:
                        return True
            return False
        except Exception:
            return True

    def restore_focus(self):
        if self.is_switching:
            return
            
        if getattr(self, 'skip_focus_restore', False):
            self.skip_focus_restore = False
            self.last_active_app = None
            return
            
        if self.last_active_app:
            try:
                from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps
                ws = NSWorkspace.sharedWorkspace()
                curr_app = ws.frontmostApplication()
                if curr_app and curr_app.processIdentifier() == os.getpid():
                    pid = self.last_active_app.processIdentifier()
                    
                    if self._app_has_windows_on_current_space(pid):
                        # focus drops here, had to hack in NSApplicationActivateIgnoringOtherApps
                        self.last_active_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                    else:
                        for app in ws.runningApplications():
                            if app.bundleIdentifier() == "com.apple.finder":
                                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                                break
                    
                    self.last_active_app = None
            except Exception:
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
                except Exception: continue
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

    def isolate_plugin_crash(self, plugin_id, error_msg):
        print(f"ktools: isolating crash in plugin {plugin_id}")
        if plugin_id in self.plugins:
            try:
                p_inst = self.plugins[plugin_id]
                target_win = getattr(p_inst, 'shell', getattr(p_inst, 'window', getattr(p_inst, 'monitor', None)))
                if target_win:
                    target_win.hide()
                    target_win.deleteLater()
                if hasattr(p_inst, 'unload'):
                    p_inst.unload()
                del self.plugins[plugin_id]
                if plugin_id in sys.modules:
                    del sys.modules[plugin_id]
            except Exception as e:
                print(f"ktools: error during crash isolation of {plugin_id}: {e}")
        
        self.notify(f"plugin {plugin_id} crashed!\ncheck logs. it was unloaded.")
        self.add_log(f"CRASH ISOLATED: {plugin_id}\n{error_msg}")
        self.refresh_menu()

    def run(self): 
        sys.exit(self.app.exec())

if __name__ == "__main__":
    ktools().run()
