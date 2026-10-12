import json
import re
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt,QThread,QTimer,Signal
from PySide6.QtGui import QTextCursor,QKeySequence,QShortcut,QAction,QTextDocument
from PySide6.QtWidgets import (
    QApplication,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QFrame,QHBoxLayout,
    QHeaderView,QInputDialog,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMainWindow,
    QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QSpinBox,QStackedWidget,
    QTableWidget,QTableWidgetItem,QTextBrowser,QVBoxLayout,QWidget,QMenu,QScrollArea,
)
from inferlm import __version__
from inferlm.core.services import Services
from inferlm.core.types import GIB,Settings
from inferlm.gui.jobs import Worker
from inferlm.gui.theme import stylesheet,colors,document_style
from inferlm.gui.commands import CommandPalette
from inferlm.gui.icons import icon
from inferlm.hardware.detect import detect
from inferlm.hardware.memory import plan
from inferlm.optimization.benchmark import run as benchmark
from inferlm.optimization.search import optimize

def button(text,action,primary=False):
    b = QPushButton(text)
    b.clicked.connect(action)
    b.setAccessibleName(text.replace("&&","&"))
    if primary:
        b.setObjectName("primary")
    return b

def label(text,name=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget

def row(*widgets):
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout

class Transcript(QTextBrowser):
    def setMarkdown(self,text):
        # Convert Qt's Markdown to HTML so paragraph/role spacing follows the theme.
        doc = QTextDocument()
        doc.setMarkdown(text,QTextDocument.MarkdownFeature.MarkdownNoHTML)
        html = doc.toHtml().split("<body",1)[1].split(">",1)[1].rsplit("</body>",1)[0]
        html = re.sub(r'(<(?:p|h[1-6]|ul|ol|li|pre|blockquote)) style="[^"]*"',r"\1",html)
        html = re.sub(r'font-size:[^;"]+;?',"",html)
        self.setHtml(html)

class Composer(QPlainTextEdit):
    send = Signal()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.send.emit()
        else:
            super().keyPressEvent(event)

class Window(QMainWindow):
    def __init__(self,services:Services):
        super().__init__()
        self.s = services
        self.job_thread:QThread|None = None
        self.worker:Worker|None = None
        self.busy_controls:list[QWidget] = []
        self.busy_actions:list[QAction] = []
        self.conversation_id,self.base_markdown,self.stream_text = "","",""
        self.rendered_length,self.closing = 0,False
        self.hardware_snapshot = None
        self.setWindowTitle("InferLM · Local workspace")
        self.resize(1320,840)
        self.setMinimumSize(860,620)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(232)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14,20,14,16)
        side.setSpacing(12)
        brand = QHBoxLayout()
        brand.addWidget(label("[i]","brandMark"))
        brand.addWidget(label("InferLM","brand"))
        brand.addStretch()
        brand.addWidget(label(__version__,"hint"))
        side.addLayout(brand)
        side.addSpacing(8)
        self.nav = QListWidget()
        self.nav.setObjectName("navigation")
        self.nav.addItems(["Chat","Models","Optimize","Benchmarks","Settings"])
        self.nav.setFixedHeight(232)
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.setAccessibleName("Main navigation")
        side.addWidget(self.nav)
        side.addSpacing(10)
        session_heading = QHBoxLayout()
        session_heading.addWidget(label("SESSIONS","eyebrow"))
        session_heading.addStretch()
        self.session_menu = self.action_menu("Session actions",[
            ("Rename session",self.rename_chat), ("Export session…",self.export_chat),
            ("Delete session…",self.delete_chat)])
        session_heading.addWidget(self.session_menu)
        side.addLayout(session_heading)
        new_session = self.controlled(button("+ New session",self.new_chat))
        new_session.setToolTip("New session · Ctrl+N")
        side.addWidget(new_session)
        self.session_search = QLineEdit()
        self.session_search.setObjectName("sessionSearch")
        self.session_search.setPlaceholderText("Search sessions…")
        self.session_search.setAccessibleName("Search saved sessions")
        self.session_search.textChanged.connect(self.filter_conversations)
        side.addWidget(self.session_search)
        self.conversations = QListWidget()
        self.conversations.setObjectName("sessions")
        self.conversations.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.conversations.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.conversations.setAccessibleName("Saved conversations")
        self.conversations.itemClicked.connect(self.open_session)
        side.addWidget(self.conversations,1)
        self.session_empty = label("No saved sessions yet.","hint")
        side.addWidget(self.session_empty)
        self.device_summary = label("Inspecting this device…","hint")
        side.addWidget(label("THIS DEVICE","eyebrow"))
        side.addWidget(self.device_summary)
        side.addSpacing(6)
        side.addWidget(button("Commands    Ctrl+P",self.show_commands))
        outer.addWidget(self.sidebar)
        body = QVBoxLayout()
        body.setContentsMargins(0,0,0,0)
        body.setSpacing(0)
        header = QFrame()
        header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20,10,20,10)
        toggle = button("☰",self.toggle_sidebar)
        toggle.setObjectName("ghost")
        toggle.setAccessibleName("Toggle sidebar")
        toggle.setToolTip("Toggle sidebar · Ctrl+B")
        header_layout.addWidget(toggle)
        self.breadcrumb = label("workspace / chat","breadcrumb")
        header_layout.addWidget(self.breadcrumb,1)
        self.status = label("○  No model loaded","status")
        self.status.setMaximumWidth(300)
        self.status.setWordWrap(False)
        header_layout.addWidget(self.status)
        body.addWidget(header)
        self.pages = QStackedWidget()
        body.addWidget(self.pages,1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        body.addWidget(self.progress)
        taskbar = QFrame()
        taskbar.setObjectName("taskbar")
        task_layout = QHBoxLayout(taskbar)
        task_layout.setContentsMargins(20,8,20,8)
        self.feedback = label("Add a GGUF model to get started.","hint")
        self.feedback.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        task_layout.addWidget(self.feedback,1)
        self.stop_button = button("Stop · Esc",self.stop)
        self.stop_button.setAccessibleName("Stop current task")
        self.stop_button.setEnabled(False)
        self.stop_button.hide()
        task_layout.addWidget(self.stop_button)
        body.addWidget(taskbar)
        outer.addLayout(body,1)
        self.make_chat()
        self.make_models()
        self.make_optimize()
        self.make_benchmarks()
        self.make_settings()
        self.nav.currentRowChanged.connect(self.navigate)
        self.nav.setCurrentRow(0)
        self.shortcuts = []
        for key,action in [("Ctrl+P",self.show_commands),("Ctrl+B",self.toggle_sidebar),
                           ("Ctrl+N",self.new_chat),("Escape",self.stop)]:
            shortcut = QShortcut(QKeySequence(key),self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)
        for index in range(5):
            shortcut = QShortcut(QKeySequence("Ctrl+"+str(index+1)),self)
            shortcut.activated.connect(lambda index=index:self.nav.setCurrentRow(index))
            self.shortcuts.append(shortcut)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.flush_stream)
        self.timer.start(80)
        self.refresh_models()
        self.refresh_conversations()
        self.refresh_reports()
        self.apply_theme(self.s.config()["theme"])
        QTimer.singleShot(0,self.refresh_hardware)

    def action_menu(self,name,actions):
        control = button("···",lambda:None)
        control.setObjectName("ghost")
        control.setAccessibleName(name)
        control.setToolTip(name)
        menu = QMenu(control)
        for title,callback in actions:
            action = menu.addAction(title)
            action.triggered.connect(callback)
            self.busy_actions.append(action)
        control.setMenu(menu)
        return control

    def apply_theme(self,theme):
        self.setStyleSheet(stylesheet(theme))
        for index in range(5):
            self.nav.item(index).setIcon(icon(index,colors(theme)["muted"]))
        self.transcript.document().setDefaultStyleSheet(document_style(theme))
        self.transcript.document().setDocumentMargin(18)
        self.transcript.setMarkdown(self.base_markdown)

    def change_theme(self,theme):
        self.apply_theme(theme)
        self.s.save_config({"theme":theme})
        self.feedback.setText("Appearance saved.")

    def navigate(self,index):
        if index < 0:
            return
        self.pages.setCurrentIndex(index)
        self.breadcrumb.setText("workspace / "+["chat","models","optimize","benchmarks","settings"][index])

    def toggle_sidebar(self):
        self.sidebar.setVisible(self.sidebar.isHidden())

    def open_session(self,item):
        self.nav.setCurrentRow(0)
        self.open_conversation(item)

    def show_commands(self):
        commands:list[tuple[str,str,Callable]] = [("Open "+name,"Ctrl+"+str(i+1),lambda i=i:self.nav.setCurrentRow(i))
                    for i,name in enumerate(["Chat","Models","Optimize","Benchmarks","Settings"])]
        commands.append(("Toggle sidebar","Ctrl+B",self.toggle_sidebar))
        if self.job_thread is None:
            commands.extend([("New session","Ctrl+N",self.new_chat),
                ("Import GGUF model…","",self.add_model),("Load selected model","",self.load_model),
                ("Unload model","",self.unload),("Export current session…","",self.export_chat),
                ("Copy last answer","",self.copy_answer),("Run benchmark","",self.run_benchmark),
                ("Quick tune","",lambda:self.tune("quick"))])
        else:
            commands.append(("Stop current task","Esc",self.stop))
        CommandPalette(self,commands).exec()

    def controlled(self,widget):
        self.busy_controls.append(widget)
        return widget

    def page(self,title,subtitle):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(28,28,28,28)
        layout.setSpacing(16)
        layout.addWidget(label(title,"title"))
        layout.addWidget(label(subtitle,"subtitle"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        self.pages.addWidget(scroll)
        return layout

    def make_chat(self):
        page = QWidget()
        self.pages.addWidget(page)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(24,18,24,14)
        page_layout.setSpacing(12)
        heading = QHBoxLayout()
        self.session_title = label("New session","sessionTitle")
        heading.addWidget(self.session_title,1)
        self.message_menu = self.action_menu("Message actions",[
            ("Copy last answer",self.copy_answer),("Copy code block",self.copy_code),
            ("Retry last answer",self.retry),("Edit last prompt",self.edit_prompt),
            ("Trim older turns…",self.trim_history)])
        heading.addWidget(self.message_menu)
        page_layout.addLayout(heading)
        content_row = QHBoxLayout()
        content_row.setContentsMargins(0,0,0,0)
        content_row.addStretch(1)
        column = QWidget()
        column.setMaximumWidth(900)
        content = QVBoxLayout(column)
        content.setContentsMargins(0,0,0,0)
        content.setSpacing(10)
        self.chat_surface = QStackedWidget()
        welcome = QWidget()
        intro = QVBoxLayout(welcome)
        intro.setContentsMargins(24,24,24,24)
        intro.addStretch(2)
        wordmark = label("InferLM","wordmark")
        wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.addWidget(wordmark)
        motto = label("Local intelligence. Your machine.","subtitle")
        motto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.addWidget(motto)
        intro.addSpacing(24)
        for text,callback in [("01   Import a GGUF model     →",self.add_model),
                              ("02   Set up your runtime    →",lambda:self.nav.setCurrentRow(4)),
                              ("03   Find the right settings →",lambda:self.nav.setCurrentRow(2))]:
            action = self.controlled(button(text,callback))
            action.setObjectName("suggestion")
            intro.addWidget(action)
        intro.addSpacing(16)
        note = label("On-device chat · No account needed","hint")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        intro.addWidget(note)
        intro.addStretch(3)
        self.chat_surface.addWidget(welcome)
        self.transcript = Transcript()
        self.transcript.setObjectName("transcript")
        self.transcript.setOpenExternalLinks(False)
        self.transcript.anchorClicked.connect(self.open_link)
        self.transcript.setAccessibleName("Conversation transcript")
        self.chat_surface.addWidget(self.transcript)
        content.addWidget(self.chat_surface,1)
        frame = QFrame()
        frame.setObjectName("composerFrame")
        composer_layout = QVBoxLayout(frame)
        composer_layout.setContentsMargins(12,8,12,10)
        composer_layout.setSpacing(8)
        self.composer = Composer()
        self.composer.setObjectName("composer")
        self.composer.setPlaceholderText("Ask anything. It runs here.")
        self.composer.setAccessibleName("Message input")
        self.composer.setMinimumHeight(64)
        self.composer.setMaximumHeight(100)
        self.composer.send.connect(self.send)
        composer_layout.addWidget(self.composer)
        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(170)
        self.model_combo.setMaximumWidth(320)
        self.model_combo.setAccessibleName("Chat model")
        self.model_combo.setToolTip("Select a local model")
        self.model_combo.currentIndexChanged.connect(self.model_changed)
        self.busy_controls.append(self.model_combo)
        footer.addWidget(self.model_combo,1)
        self.load_button = self.controlled(button("Load",self.load_model))
        self.load_button.setAccessibleName("Load model")
        footer.addWidget(self.load_button)
        self.unload_button = self.controlled(button("Unload",self.unload))
        footer.addWidget(self.unload_button)
        footer.addStretch()
        self.send_button = self.controlled(button("↑",self.send,True))
        self.send_button.setAccessibleName("Send message")
        self.send_button.setToolTip("Send message · Enter")
        self.send_button.setFixedWidth(40)
        footer.addWidget(self.send_button)
        composer_layout.addLayout(footer)
        content.addWidget(frame)
        hints = QHBoxLayout()
        send_hint = label("Enter send   ·   Shift+Enter newline","hint")
        send_hint.setWordWrap(False)
        hints.addWidget(send_hint,1)
        hints.addStretch()
        command_hint = label("Ctrl+P commands","hint")
        command_hint.setWordWrap(False)
        hints.addWidget(command_hint)
        content.addLayout(hints)
        content_row.addWidget(column,8)
        content_row.addStretch(1)
        page_layout.addLayout(content_row,1)

    def make_models(self):
        page = self.page("Models","Local GGUF files. Import, inspect, and load.")
        page.addLayout(row(self.controlled(button("Add GGUF model…",self.add_model,True)),
                           self.controlled(button("Relink selected…",self.relink_model)),
                           self.controlled(button("Remove from library",self.remove_model))))
        self.model_table = QTableWidget(0,5)
        self.model_table.setHorizontalHeaderLabels(["Model","Size","Architecture","Quantization","File"])
        self.model_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.model_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.setAlternatingRowColors(True)
        self.model_table.setMinimumHeight(220)
        self.model_table.verticalHeader().hide()
        self.model_table.verticalHeader().setDefaultSectionSize(44)
        self.model_table.itemSelectionChanged.connect(self.show_model_details)
        page.addWidget(self.model_table,1)
        self.model_details = QTextBrowser()
        self.model_details.setMaximumHeight(210)
        self.model_details.setMarkdown("Drop a .gguf file here or use **Add GGUF model**.")
        page.addWidget(self.model_details)

    def make_optimize(self):
        page = self.page("Optimize","Measure before changing. Compare settings on this device.")
        self.hardware_label = label("Inspecting hardware…","subtitle")
        self.memory_label = label("Select a model for an estimated memory plan.","subtitle")
        page.addWidget(self.hardware_label)
        page.addWidget(self.memory_label)
        controls = QHBoxLayout()
        def spin(name,minimum,maximum,value):
            box = QSpinBox()
            box.setRange(minimum,maximum)
            box.setValue(value)
            box.setAccessibleName(name)
            group = QVBoxLayout()
            group.addWidget(label(name,"eyebrow"))
            group.addWidget(box)
            controls.addLayout(group)
            self.busy_controls.append(box)
            box.valueChanged.connect(self.update_memory)
            return box
        self.context = spin("Context tokens",256,131072,2048)
        self.cpu_threads = spin("CPU threads",1,256,4)
        self.gpu_layers = spin("GPU layers",0,1000,0)
        self.batch = spin("Batch",16,8192,256)
        self.ubatch = spin("Microbatch",16,8192,128)
        page.addLayout(controls)
        self.budget = QSpinBox()
        self.budget.setRange(30,7200)
        self.budget.setValue(900)
        self.budget.setSuffix(" seconds")
        self.budget.setAccessibleName("Tuning time budget")
        self.busy_controls.append(self.budget)
        page.addLayout(row(self.controlled(button("Quick Tune · up to 6",lambda:self.tune("quick"),True)),
                           self.controlled(button("Thorough Tune · up to 12",lambda:self.tune("thorough"))),
                           self.controlled(button("Run benchmark",self.run_benchmark))))
        budget_row = QHBoxLayout()
        budget_row.addWidget(label("Time budget","subtitle"))
        self.budget.setMaximumWidth(180)
        budget_row.addWidget(self.budget)
        budget_row.addStretch()
        page.addLayout(budget_row)
        page.addWidget(label("Tuning temporarily unloads the chat model. Cancellation preserves your active settings.","subtitle"))
        page.addWidget(label("SAVED PROFILES","eyebrow"))
        self.profile_empty = label("No measured profiles yet. Run a benchmark, then tune.","hint")
        page.addWidget(self.profile_empty)
        self.profile_list = QListWidget()
        self.profile_list.setAccessibleName("Saved optimization profiles")
        self.profile_list.setMinimumHeight(140)
        page.addWidget(self.profile_list,1)
        page.addLayout(row(self.controlled(button("Apply selected profile",self.apply_profile)),
                           self.controlled(button("Restore profile baseline",self.restore_baseline)),
                           self.controlled(button("Save manual settings",self.save_manual))))
        self.tuning_log = QPlainTextEdit()
        self.tuning_log.setReadOnly(True)
        self.tuning_log.document().setMaximumBlockCount(150)
        self.tuning_log.setMaximumHeight(145)
        page.addWidget(self.tuning_log)

    def make_benchmarks(self):
        page = self.page("Benchmarks","Recorded measurements for each model, runtime, and device.")
        self.report_list = QListWidget()
        self.report_list.setMaximumHeight(150)
        self.report_list.itemClicked.connect(self.show_report)
        self.report_list.setAccessibleName("Measured benchmark runs")
        page.addWidget(self.report_list)
        self.report_view = QTextBrowser()
        self.report_view.setMinimumHeight(260)
        self.report_view.setPlainText("No measured runs yet. Run a benchmark from Optimize.")
        page.addWidget(self.report_view,1)
        page.addWidget(self.controlled(button("Export selected JSON…",self.export_report)),
                       alignment=Qt.AlignmentFlag.AlignRight)

    def make_settings(self):
        page = self.page("Settings","Runtime, appearance, and local generation preferences.")
        cfg = self.s.config()
        form = QFormLayout()
        self.runtime_path = QLineEdit(cfg["runtime_folder"])
        self.runtime_path.setPlaceholderText("Folder containing llama-server and llama-bench")
        self.runtime_path.setAccessibleName("Runtime folder")
        directory = QWidget()
        layout = QHBoxLayout(directory)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.runtime_path,1)
        layout.addWidget(self.controlled(button("Browse…",self.choose_runtime)))
        form.addRow("llama.cpp runtime",directory)
        self.theme = QComboBox()
        self.theme.addItems(["dark","light"])
        self.theme.setCurrentText(cfg["theme"])
        self.theme.currentTextChanged.connect(self.change_theme)
        form.addRow("Theme",self.theme)
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0,2)
        self.temperature.setSingleStep(.1)
        self.temperature.setValue(cfg["temperature"])
        form.addRow("Temperature",self.temperature)
        self.answer_limit = QSpinBox()
        self.answer_limit.setRange(16,8192)
        self.answer_limit.setValue(cfg["max_tokens"])
        form.addRow("Maximum answer tokens",self.answer_limit)
        self.ram_reserve = QSpinBox()
        self.ram_reserve.setRange(2,64)
        self.ram_reserve.setSuffix(" GiB")
        self.ram_reserve.setValue(cfg["reserve_gib"])
        form.addRow("Minimum RAM reserve",self.ram_reserve)
        self.system_prompt = QPlainTextEdit(cfg["system_prompt"])
        self.system_prompt.setMaximumHeight(90)
        form.addRow("System instruction",self.system_prompt)
        page.addLayout(form)
        self.busy_controls.extend([self.runtime_path,self.theme,self.temperature,self.answer_limit,
                                   self.ram_reserve,self.system_prompt])
        page.addLayout(row(self.controlled(button("Validate runtime && save",self.save_config,True)),
                           self.controlled(button("Download pinned CPU runtime…",self.install_runtime))))
        page.addWidget(label("CPU is the starting point. CUDA requires a compatible NVIDIA device and build. "
                             "Vulkan is experimental; detecting a GPU does not verify acceleration.","subtitle"))
        page.addWidget(label("Data location: "+str(self.s.data_dir),"subtitle"))
        page.addWidget(button("Show runtime troubleshooting log",self.show_logs))
        page.addStretch()

    def job(self,operation,on_result,description):
        if self.job_thread is not None:
            self.feedback.setText("Another task is running. Stop it first.")
            return
        self.s.cancel.clear()
        self.feedback.setText(description)
        self.status.setText("◌  Working")
        self.progress.setRange(0,0)
        self.progress.show()
        self.stop_button.setEnabled(True)
        self.stop_button.show()
        for action in self.busy_actions:
            action.setEnabled(False)
        for control in self.busy_controls:
            control.setEnabled(False)
        self.conversations.setEnabled(False)
        self.job_thread = QThread(self)
        self.worker = Worker(operation)
        self.worker.moveToThread(self.job_thread)
        self.job_thread.started.connect(self.worker.run)
        self.worker.result.connect(on_result)
        self.worker.error.connect(self.job_error)
        self.worker.progress.connect(self.job_progress)
        self.worker.chunk.connect(self.receive_chunk)
        self.worker.finished.connect(self.job_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.job_thread.finished.connect(self.job_finished)
        self.job_thread.finished.connect(self.job_thread.deleteLater)
        self.job_thread.start()

    def job_error(self,text):
        conv = self.s.db.get("conversations",self.conversation_id) if self.conversation_id else None
        if conv and conv.get("draft") and not self.composer.toPlainText():
            self.composer.setPlainText(conv["draft"])
        self.feedback.setText(text)
        self.tuning_log.appendPlainText(text)

    def job_progress(self,text):
        self.feedback.setText(text)
        self.tuning_log.appendPlainText(text)

    def job_finished(self):
        self.job_thread,self.worker = None,None
        self.progress.hide()
        self.stop_button.setEnabled(False)
        self.stop_button.hide()
        for action in self.busy_actions:
            action.setEnabled(True)
        for control in self.busy_controls:
            control.setEnabled(True)
        self.conversations.setEnabled(True)
        self.status.setText("●  Model ready" if self.s.runtime.model else "○  No model loaded")
        self.status.setToolTip(self.s.runtime.model.name if self.s.runtime.model else "Load a local GGUF model to chat.")
        self.flush_stream()
        conv = self.s.db.get("conversations",self.conversation_id) if self.conversation_id else None
        if conv:
            self.show_conversation(conv)
        self.refresh_conversations()
        self.refresh_reports()
        if self.closing:
            self.close()

    def stop(self):
        if self.job_thread is None:
            return
        self.feedback.setText("Stopping current task…")
        self.s.stop_job()

    def selected_model(self):
        id = self.model_combo.currentData()
        if not id:
            raise ValueError("Add and select a GGUF model first.")
        return self.s.model(id)

    def current_settings(self):
        settings = Settings(self.context.value(),self.cpu_threads.value(),self.gpu_layers.value(),
                            self.batch.value(),self.ubatch.value())
        settings.validate()
        return settings

    def model_changed(self,*_):
        if not hasattr(self,"context") or not self.model_combo.currentData():
            return
        settings = self.s.settings(self.model_combo.currentData())
        for control,value in ((self.context,settings.context),(self.cpu_threads,settings.threads),
                              (self.gpu_layers,settings.gpu_layers),(self.batch,settings.batch),
                              (self.ubatch,settings.ubatch)):
            control.blockSignals(True)
            control.setValue(value)
            control.blockSignals(False)
        self.update_memory()

    def refresh_models(self):
        selected = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.setPlaceholderText("Select a local model…")
        models = self.s.models()
        self.model_table.setRowCount(len(models))
        for i,model in enumerate(models):
            self.model_combo.addItem(model.name,model.id)
            values = [model.name,f"{model.size/GIB:.2f} GiB",model.architecture,model.quantization,
                      "Present" if Path(model.path).is_file() else "Missing"]
            for col,value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole,model.id)
                self.model_table.setItem(i,col,item)
        index = self.model_combo.findData(selected)
        if index>=0:
            self.model_combo.setCurrentIndex(index)
        self.model_combo.blockSignals(False)
        self.model_changed()

    def refresh_hardware(self):
        self.job(lambda p,c:detect(self.s.data_dir),self.hardware_ready,"Inspecting local hardware…")

    def hardware_ready(self,hw):
        self.hardware_snapshot = hw
        self.hardware_label.setText(f"{hw.cpu} · {hw.physical_cores} cores · "
                                   f"{hw.ram_available/GIB:.1f}/{hw.ram_total/GIB:.1f} GiB RAM available\n"
                                   +(" · ".join(g.name for g in hw.gpus) or hw.gpu_status))
        self.device_summary.setText(f"{hw.physical_cores} CPU cores · {hw.ram_total/GIB:.0f} GiB RAM\n"
                                    +(" / ".join(g.name for g in hw.gpus) or "CPU runtime available"))
        self.feedback.setText("Device ready. Add a model or continue a saved session.")
        self.update_memory()

    def update_memory(self,*_):
        if not hasattr(self,"memory_label") or not self.model_combo.currentData():
            return
        try:
            if self.hardware_snapshot is None:
                self.memory_label.setText("Inspecting hardware in the background…")
                return
            memory = plan(self.selected_model(),self.hardware_snapshot,self.current_settings(),self.s.config()["reserve_gib"])
            amount = f"{memory.ram_required/GIB:.2f} GiB estimated RAM" if memory.ram_required else "RAM estimate unavailable"
            self.memory_label.setText(f"{memory.classification} · {amount} · {memory.reserve/GIB:.1f} GiB reserved")
        except Exception as exc:
            self.memory_label.setText(str(exc))

    def add_model(self,path=None):
        if not isinstance(path,(str,Path)):
            path,_ = QFileDialog.getOpenFileName(self,"Import local model","","GGUF (*.gguf)")
        if path:
            self.job(lambda p,c:self.s.import_model(Path(path)),self.imported,"Validating GGUF and model fingerprint…")

    def imported(self,model):
        self.refresh_models()
        self.model_combo.setCurrentIndex(self.model_combo.findData(model.id))
        self.feedback.setText("Imported "+model.name+". Weights kept at their original location.")

    def selected_table_model(self):
        items = self.model_table.selectedItems()
        if not items:
            raise ValueError("Select a model in the table.")
        return self.s.model(items[0].data(Qt.ItemDataRole.UserRole))

    def show_model_details(self):
        try:
            model = self.selected_table_model()
            if self.hardware_snapshot is None:
                return
            memory = plan(model,self.hardware_snapshot,self.current_settings(),self.s.config()["reserve_gib"])
            self.model_details.setPlainText(model.path+"\n"+memory.classification+" — Estimated\n"+"\n".join(memory.assumptions))
        except ValueError:
            pass

    def relink_model(self):
        try:
            original = self.selected_table_model()
            path,_ = QFileDialog.getOpenFileName(self,"Relink model","","GGUF (*.gguf)")
            if not path:
                return
            def operation(p,c):
                model = self.s.import_model(Path(path))
                if model.fingerprint!=original.fingerprint:
                    raise ValueError("Different weights imported separately. Original entry kept.")
                return model
            self.job(operation,self.imported,"Validating replacement model…")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def remove_model(self):
        try:
            model = self.selected_table_model()
            if self.s.runtime.model and self.s.runtime.model.id==model.id:
                raise ValueError("Unload the model before removing its library entry.")
            self.s.db.delete("models",model.id)
            self.refresh_models()
            self.feedback.setText("Library entry removed. Model file kept.")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def load_model(self):
        try:
            model,settings = self.selected_model(),self.current_settings()
            if self.hardware_snapshot is None:
                raise ValueError("Hardware inspection is still running.")
            memory = plan(model,self.hardware_snapshot,settings,self.s.config()["reserve_gib"])
            allow = False
            if memory.classification=="Not enough information":
                allow = QMessageBox.question(self,"Incomplete memory estimate",
                    "No reliable estimate is available. Attempt an unverified load?",
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
                if not allow:
                    return
            self.job(lambda p,c:self.s.load(model.id,settings,allow),
                     lambda _:self.feedback.setText("Model loaded. Local chat ready."),"Loading "+model.name+"…")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def unload(self):
        self.job(lambda p,c:self.s.runtime.stop(),lambda _:self.feedback.setText("Model unloaded."),"Unloading…")

    def new_chat(self):
        if self.job_thread is not None:
            return
        self.nav.setCurrentRow(0)
        try:
            conv = self.s.new_conversation(self.selected_model().id)
            self.conversation_id = conv["id"]
            self.composer.clear()
            self.refresh_conversations()
            self.show_conversation(conv)
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def refresh_conversations(self):
        self.conversations.clear()
        for conv in self.s.db.list("conversations"):
            item = QListWidgetItem(conv["title"])
            item.setData(Qt.ItemDataRole.UserRole,conv["id"])
            item.setToolTip(conv["title"])
            self.conversations.addItem(item)
            if conv["id"]==self.conversation_id:
                self.conversations.setCurrentItem(item)
        self.filter_conversations()

    def filter_conversations(self,*_):
        query = self.session_search.text().casefold()
        visible = 0
        for i in range(self.conversations.count()):
            item = self.conversations.item(i)
            matched = query in item.text().casefold()
            item.setHidden(not matched)
            visible += int(matched)
        self.session_empty.setText("No matching sessions." if query else "No saved sessions yet.")
        self.session_empty.setVisible(visible == 0)

    def open_conversation(self,item):
        self.conversation_id = item.data(Qt.ItemDataRole.UserRole)
        conv = self.s.db.get("conversations",self.conversation_id)
        if conv:
            self.model_combo.setCurrentIndex(self.model_combo.findData(conv["model_id"]))
            self.show_conversation(conv)
            self.composer.setPlainText(conv.get("draft",""))

    def show_conversation(self,conv):
        self.session_title.setText(conv["title"])
        self.chat_surface.setCurrentIndex(1 if conv["messages"] else 0)
        self.base_markdown = "\n\n".join("### "+("You" if m["role"]=="user" else "InferLM")+"\n\n"+m["content"]+
            ("\n\n*"+m["state"]+"*" if m["state"] not in ("complete","generating") else "") for m in conv["messages"])
        self.stream_text,self.rendered_length = "",0
        self.transcript.setMarkdown(self.base_markdown or "## New conversation\n\nAsk your local model a question.")

    def send(self):
        if self.job_thread is not None:
            return
        text = self.composer.toPlainText().strip()
        if not text:
            return
        try:
            model = self.selected_model()
            if not self.s.runtime.model or self.s.runtime.model.id!=model.id:
                raise ValueError("Load the selected model first.")
            conv = self.s.db.get("conversations",self.conversation_id) if self.conversation_id else None
            if not conv or conv["model_id"]!=model.id:
                self.new_chat()
                conv = self.s.db.get("conversations",self.conversation_id)
            self.show_conversation(conv)
            self.chat_surface.setCurrentIndex(1)
            self.base_markdown += "\n\n### You\n\n"+text+"\n\n### InferLM\n\n"
            self.transcript.setMarkdown(self.base_markdown)
            self.composer.clear()
            conversation_id = self.conversation_id
            self.job(lambda p,c:self.s.chat(conversation_id,text,c),self.chat_done,"Generating locally…")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def receive_chunk(self,text):
        self.stream_text += text

    def flush_stream(self):
        if len(self.stream_text)>self.rendered_length:
            scroll = self.transcript.verticalScrollBar()
            near_bottom = scroll.maximum()-scroll.value()<60
            cursor = self.transcript.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(self.stream_text[self.rendered_length:])
            self.rendered_length = len(self.stream_text)
            if near_bottom:
                scroll.setValue(scroll.maximum())

    def chat_done(self,result):
        self.feedback.setText(f"Measured first token: {result['ttft_seconds']:.2f}s · "
                              f"request: {result['request_seconds']:.2f}s · saved locally")
        conv = self.s.db.get("conversations",self.conversation_id)
        if conv:
            self.show_conversation(conv)

    def rename_chat(self):
        if not self.conversation_id:
            return
        conv = self.s.db.get("conversations",self.conversation_id)
        if not conv:
            return
        title,ok = QInputDialog.getText(self,"Rename conversation","Name:",text=conv["title"])
        if ok and title.strip():
            conv["title"] = title.strip()[:120]
            self.s.db.put("conversations",self.conversation_id,conv)
            self.refresh_conversations()
            self.session_title.setText(conv["title"])

    def delete_chat(self):
        if self.conversation_id and QMessageBox.question(self,"Delete conversation","Delete the saved conversation?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.s.db.delete("conversations",self.conversation_id)
            self.conversation_id,self.base_markdown,self.stream_text = "","",""
            self.refresh_conversations()
            self.transcript.clear()
            self.composer.clear()
            self.session_title.setText("New session")
            self.chat_surface.setCurrentIndex(0)

    def export_chat(self):
        if self.conversation_id:
            path,_ = QFileDialog.getSaveFileName(self,"Export conversation","conversation.md","Markdown (*.md);;JSON (*.json)")
            if path:
                self.s.export_conversation(self.conversation_id,Path(path))
                self.feedback.setText("Conversation exported.")

    def copy_answer(self):
        conv = self.s.db.get("conversations",self.conversation_id)
        if conv:
            answers = [m["content"] for m in conv["messages"] if m["role"]=="assistant"]
            if answers:
                QApplication.clipboard().setText(answers[-1])
                self.feedback.setText("Last answer copied.")

    def copy_code(self):
        conv = self.s.db.get("conversations",self.conversation_id)
        if conv:
            content = "\n".join(m["content"] for m in conv["messages"] if m["role"]=="assistant")
            blocks = re.findall(r"```[^\n]*\n(.*?)```",content,re.S)
            if blocks:
                QApplication.clipboard().setText(blocks[-1])
                self.feedback.setText("Latest code block copied.")
            else:
                self.feedback.setText("No fenced code block found.")

    def edit_prompt(self):
        try:
            self.composer.setPlainText(self.s.retry(self.conversation_id))
            self.show_conversation(self.s.db.get("conversations",self.conversation_id))
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def retry(self):
        self.edit_prompt()
        self.send()

    def trim_history(self):
        if not self.conversation_id:
            return
        if QMessageBox.question(self,"Shorter conversation",
            "Create a shorter branch? Oldest turns will be omitted; your latest question, system instruction "
            "and original conversation will be kept.",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        id = self.conversation_id
        def ready(conv):
            self.conversation_id = conv["id"]
            self.show_conversation(conv)
            self.composer.setPlainText(conv.get("draft",""))
            self.feedback.setText("Shorter branch created. Original conversation kept.")
        self.job(lambda p,c:self.s.trim_conversation(id),ready,"Counting tokens and trimming older turns…")

    def save_manual(self):
        try:
            model = self.selected_model()
            self.s.db.put("active_settings",model.id,asdict(self.current_settings()))
            self.feedback.setText("Manual settings saved. Reload to apply; this is not measured optimization.")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def tune(self,mode):
        try:
            model,budget = self.selected_model(),self.budget.value()
            self.s.db.put("active_settings",model.id,asdict(self.current_settings()))
            self.tuning_log.clear()
            self.job(lambda p,c:optimize(self.s,model.id,mode,budget,p),
                     lambda profile:self.feedback.setText(profile["conclusion"]),"Starting "+mode+" tuning…")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def run_benchmark(self):
        try:
            model,settings,budget = self.selected_model(),self.current_settings(),self.budget.value()
            self.job(lambda p,c:benchmark(self.s,model,settings,p,budget),
                     lambda report:self.feedback.setText("Measured benchmark saved: "+report["id"]),"Running benchmarks…")
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def refresh_reports(self):
        self.report_list.clear()
        for report in self.s.db.list("benchmarks"):
            item = QListWidgetItem(f"{report['timestamp'][:19]} · Measured · {report['native']['generation_score']:.2f} tok/s")
            item.setData(Qt.ItemDataRole.UserRole,report["id"])
            self.report_list.addItem(item)
        self.profile_list.clear()
        for profile in self.s.db.list("profiles"):
            item = QListWidgetItem(profile["conclusion"])
            item.setData(Qt.ItemDataRole.UserRole,profile["id"])
            self.profile_list.addItem(item)
        self.profile_empty.setVisible(self.profile_list.count()==0)

    def show_report(self,item):
        report = self.s.db.get("benchmarks",item.data(Qt.ItemDataRole.UserRole))
        self.report_view.setPlainText(json.dumps(report,indent=2,ensure_ascii=False))

    def export_report(self):
        item = self.report_list.currentItem()
        if item:
            path,_ = QFileDialog.getSaveFileName(self,"Export benchmark","benchmark.json","JSON (*.json)")
            if path:
                record = self.s.db.get("benchmarks",item.data(Qt.ItemDataRole.UserRole))
                Path(path).write_text(json.dumps(record,indent=2),encoding="utf-8")
                self.feedback.setText("Measured benchmark exported.")

    def apply_profile(self):
        item = self.profile_list.currentItem()
        if item:
            id = item.data(Qt.ItemDataRole.UserRole)
            def applied(settings):
                self.model_changed()
                self.feedback.setText("Profile saved. Reload model to apply.")
            self.job(lambda p,c:self.s.apply_profile(id),applied,"Validating measured profile…")

    def restore_baseline(self):
        item = self.profile_list.currentItem()
        if item:
            record = self.s.db.get("profiles",item.data(Qt.ItemDataRole.UserRole))
            if not record:
                return
            self.s.db.put("active_settings",record["model_id"],record["baseline_settings"])
            self.model_changed()
            self.feedback.setText("Baseline settings restored. Reload to apply.")

    def choose_runtime(self):
        folder = QFileDialog.getExistingDirectory(self,"Choose llama.cpp folder")
        if folder:
            self.runtime_path.setText(folder)

    def save_config(self):
        from inferlm.runtime.capabilities import binaries,inspect
        cfg = {"runtime_folder":self.runtime_path.text().strip(),"theme":self.theme.currentText(),
               "temperature":self.temperature.value(),"max_tokens":self.answer_limit.value(),
               "reserve_gib":self.ram_reserve.value(),"system_prompt":self.system_prompt.toPlainText()}
        def operation(p,c):
            server,bench = binaries(str(cfg["runtime_folder"]))
            caps = inspect(server)
            inspect(bench)
            self.s.save_config(cfg)
            return caps.version
        def saved(version):
            self.apply_theme(cfg["theme"])
            self.update_memory()
            self.feedback.setText("Settings saved. Runtime: "+version.split("\n")[0])
        self.job(operation,saved,"Validating runtime…")

    def install_runtime(self):
        from inferlm.runtime.install import install
        destination = self.s.data_dir/"runtimes"/"llama-b11564-cpu"
        if destination.is_dir():
            self.runtime_path.setText(str(destination))
            self.feedback.setText("Runtime already installed. Validate runtime && save to use it.")
            return
        if QMessageBox.question(self,"Download CPU runtime",
            "Download the verified official llama.cpp b11564 CPU runtime (about 20 MB)? No model is downloaded.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:
            return
        def installed(path):
            self.runtime_path.setText(str(path))
            self.feedback.setText("CPU runtime installed. Validate runtime && save to use it.")
        self.job(lambda p,c:install(destination,self.s.cancel),installed,"Downloading and verifying CPU runtime…")

    def show_logs(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Local runtime log")
        dialog.setText("Recent messages. InferLM does not log your prompt text.")
        dialog.setDetailedText("\n".join(self.s.runtime.logs) or "No runtime messages.")
        dialog.exec()

    def open_link(self,url):
        if url.scheme() in ("http","https") and QMessageBox.question(self,"Open external link",
            "Open this link in your browser? This leaves the local app.",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(url)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".gguf") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self,event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile().lower().endswith(".gguf")]
        if paths and not self.job_thread:
            self.add_model(paths[0])
            event.acceptProposedAction()

    def closeEvent(self,event):
        if self.job_thread:
            self.closing = True
            self.stop()
            event.ignore()
            return
        self.timer.stop()
        self.s.close()
        event.accept()

