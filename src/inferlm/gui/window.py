import json
import re
from dataclasses import asdict
from pathlib import Path
from PySide6.QtCore import Qt,QThread,QTimer,Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QFrame,QHBoxLayout,
    QHeaderView,QInputDialog,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMainWindow,
    QMessageBox,QPlainTextEdit,QProgressBar,QPushButton,QSpinBox,QSplitter,QStackedWidget,
    QTableWidget,QTableWidgetItem,QTextBrowser,QVBoxLayout,QWidget,
)
from inferlm import __version__
from inferlm.core.services import Services
from inferlm.core.types import GIB,Settings
from inferlm.gui.jobs import Worker
from inferlm.gui.theme import stylesheet
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
    widget.setWordWrap(True)
    widget.setObjectName(name)
    return widget

def row(*widgets):
    layout = QHBoxLayout()
    for widget in widgets:
        layout.addWidget(widget)
    return layout

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
        self.conversation_id,self.base_markdown,self.stream_text = "","",""
        self.rendered_length,self.closing = 0,False
        self.hardware_snapshot = None
        self.setWindowTitle("InferLM · Local AI")
        self.resize(1280,820)
        self.setMinimumSize(960,620)
        self.setAcceptDrops(True)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(208)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20,30,20,22)
        side.addWidget(label("InferLM","brand"))
        side.addWidget(label("LOCAL. YOURS.","eyebrow"))
        side.addSpacing(32)
        self.nav = QListWidget()
        self.nav.addItems(["Chat","Models","Optimize","Benchmarks","Settings"])
        for i in range(5):
            self.nav.item(i).setIcon(icon(i))
        self.nav.setAccessibleName("Main navigation")
        side.addWidget(self.nav)
        side.addWidget(label("Your chats stay\non your laptop.","subtitle"))
        side.addSpacing(12)
        side.addWidget(label("DEVELOPMENT "+__version__,"eyebrow"))
        outer.addWidget(sidebar)
        body = QVBoxLayout()
        body.setContentsMargins(30,24,30,22)
        top = QHBoxLayout()
        top.addWidget(label("YOUR LOCAL WORKSPACE","eyebrow"))
        top.addStretch()
        self.status = label("No model loaded","status")
        top.addWidget(self.status)
        body.addLayout(top)
        self.pages = QStackedWidget()
        body.addWidget(self.pages,1)
        self.progress = QProgressBar()
        self.progress.hide()
        body.addWidget(self.progress)
        self.feedback = label("Add a local GGUF and select a llama.cpp runtime to begin.","subtitle")
        self.feedback.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.addWidget(self.feedback)
        self.stop_button = button("Stop current task",self.stop)
        self.stop_button.setEnabled(False)
        body.addWidget(self.stop_button,alignment=Qt.AlignmentFlag.AlignRight)
        outer.addLayout(body,1)
        self.make_chat()
        self.make_models()
        self.make_optimize()
        self.make_benchmarks()
        self.make_settings()
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.flush_stream)
        self.timer.start(80)
        self.refresh_models()
        self.refresh_conversations()
        self.refresh_reports()
        self.setStyleSheet(stylesheet(self.s.config()["theme"]))
        QTimer.singleShot(0,self.refresh_hardware)

    def controlled(self,widget):
        self.busy_controls.append(widget)
        return widget

    def page(self,title,subtitle):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0,18,0,0)
        layout.setSpacing(14)
        layout.addWidget(label(title,"title"))
        layout.addWidget(label(subtitle,"subtitle"))
        self.pages.addWidget(widget)
        return layout

    def make_chat(self):
        page = self.page("A conversation, on your terms.","Choose a model. Keep the conversation on your laptop.")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        self.model_combo.setAccessibleName("Chat model")
        self.model_combo.currentIndexChanged.connect(self.model_changed)
        self.busy_controls.append(self.model_combo)
        page.addLayout(row(self.model_combo,self.controlled(button("Load model",self.load_model,True)),
                           self.controlled(button("Unload",self.unload))))
        split = QSplitter()
        left = QWidget()
        sidebar = QVBoxLayout(left)
        sidebar.setContentsMargins(0,0,12,0)
        sidebar.addWidget(self.controlled(button("+ New conversation",self.new_chat)))
        self.conversations = QListWidget()
        self.conversations.setAccessibleName("Saved conversations")
        self.conversations.itemClicked.connect(self.open_conversation)
        sidebar.addWidget(self.conversations)
        for text,action in (("Rename",self.rename_chat),("Export",self.export_chat),("Delete conversation",self.delete_chat)):
            sidebar.addWidget(self.controlled(button(text,action)))
        right = QWidget()
        chat = QVBoxLayout(right)
        chat.setContentsMargins(0,0,0,0)
        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.anchorClicked.connect(self.open_link)
        self.transcript.setAccessibleName("Conversation transcript")
        self.transcript.setMarkdown("## Ready when you are\n\nAdd a GGUF in **Models** and configure your runtime in **Settings**.")
        chat.addWidget(self.transcript,1)
        chat.addLayout(row(self.controlled(button("Copy last answer",self.copy_answer)),
                           self.controlled(button("Copy code block",self.copy_code)),
                           self.controlled(button("Retry",self.retry)),
                           self.controlled(button("Edit last prompt",self.edit_prompt)),
                           self.controlled(button("Trim older turns…",self.trim_history))))
        self.composer = Composer()
        self.composer.setPlaceholderText("Message your local model… Enter sends · Shift+Enter adds a line")
        self.composer.setAccessibleName("Message input")
        self.composer.setMaximumHeight(112)
        self.composer.send.connect(self.send)
        chat.addWidget(self.composer)
        footer = QHBoxLayout()
        footer.addWidget(label("Local inference","subtitle"))
        footer.addStretch()
        footer.addWidget(self.controlled(button("Send message",self.send,True)))
        chat.addLayout(footer)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([210,760])
        page.addWidget(split,1)

    def make_models(self):
        page = self.page("Your model library.","Import an existing GGUF. Its weights stay where you put them.")
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
        self.model_table.itemSelectionChanged.connect(self.show_model_details)
        page.addWidget(self.model_table,1)
        self.model_details = QTextBrowser()
        self.model_details.setMaximumHeight(210)
        self.model_details.setMarkdown("Drop a .gguf file here or use **Add GGUF model**.")
        page.addWidget(self.model_details)

    def make_optimize(self):
        page = self.page("Find what works on this laptop.","Measured tuning: the same model, context capacity and workloads.")
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
                           self.controlled(button("Run benchmark",self.run_benchmark)),self.budget))
        page.addWidget(label("Tuning temporarily unloads the chat model. Cancellation preserves your active settings.","subtitle"))
        self.profile_list = QListWidget()
        self.profile_list.setAccessibleName("Saved optimization profiles")
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
        page = self.page("Evidence, without the guesswork.","Every result records its model, runtime, hardware and conditions.")
        self.report_list = QListWidget()
        self.report_list.setMaximumHeight(150)
        self.report_list.itemClicked.connect(self.show_report)
        self.report_list.setAccessibleName("Measured benchmark runs")
        page.addWidget(self.report_list)
        self.report_view = QTextBrowser()
        self.report_view.setPlainText("No measured runs yet. Run a benchmark from Optimize.")
        page.addWidget(self.report_view,1)
        page.addWidget(self.controlled(button("Export selected JSON…",self.export_report)),
                       alignment=Qt.AlignmentFlag.AlignRight)

    def make_settings(self):
        page = self.page("A small set of useful controls.","Choose your runtime and preferences. Data stays in your user folder.")
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
        self.status.setText("Working")
        self.progress.setRange(0,0)
        self.progress.show()
        self.stop_button.setEnabled(True)
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
        for control in self.busy_controls:
            control.setEnabled(True)
        self.conversations.setEnabled(True)
        self.status.setText("Ready · "+self.s.runtime.model.name if self.s.runtime.model else "No model loaded")
        self.flush_stream()
        conv = self.s.db.get("conversations",self.conversation_id) if self.conversation_id else None
        if conv:
            self.show_conversation(conv)
        self.refresh_conversations()
        self.refresh_reports()
        if self.closing:
            self.close()

    def stop(self):
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
        self.feedback.setText("Hardware observed locally. Performance has not been assumed.")
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
        try:
            conv = self.s.new_conversation(self.selected_model().id)
            self.conversation_id = conv["id"]
            self.refresh_conversations()
            self.show_conversation(conv)
        except ValueError as exc:
            self.feedback.setText(str(exc))

    def refresh_conversations(self):
        self.conversations.clear()
        for conv in self.s.db.list("conversations"):
            item = QListWidgetItem(conv["title"])
            item.setData(Qt.ItemDataRole.UserRole,conv["id"])
            self.conversations.addItem(item)
            if conv["id"]==self.conversation_id:
                self.conversations.setCurrentItem(item)

    def open_conversation(self,item):
        self.conversation_id = item.data(Qt.ItemDataRole.UserRole)
        conv = self.s.db.get("conversations",self.conversation_id)
        if conv:
            self.model_combo.setCurrentIndex(self.model_combo.findData(conv["model_id"]))
            self.show_conversation(conv)
            self.composer.setPlainText(conv.get("draft",""))

    def show_conversation(self,conv):
        self.base_markdown = "\n\n".join("### "+m["role"].title()+"\n\n"+m["content"]+
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
            self.base_markdown += "\n\n### You\n\n"+text+"\n\n### Assistant\n\n"
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
        title,ok = QInputDialog.getText(self,"Rename conversation","Name:",text=conv["title"])
        if ok and title.strip():
            conv["title"] = title.strip()[:120]
            self.s.db.put("conversations",self.conversation_id,conv)
            self.refresh_conversations()

    def delete_chat(self):
        if self.conversation_id and QMessageBox.question(self,"Delete conversation","Delete the saved conversation?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:
            self.s.db.delete("conversations",self.conversation_id)
            self.conversation_id,self.base_markdown,self.stream_text = "","",""
            self.refresh_conversations()
            self.transcript.setMarkdown("## Ready for a new conversation")

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
            server,bench = binaries(cfg["runtime_folder"])
            caps = inspect(server)
            inspect(bench)
            self.s.save_config(cfg)
            return caps.version
        def saved(version):
            self.setStyleSheet(stylesheet(cfg["theme"]))
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

