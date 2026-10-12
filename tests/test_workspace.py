"""Interaction regressions for the 0.2 desktop workspace."""
from PySide6.QtCore import Qt
from inferlm.gui.commands import CommandPalette
from inferlm.gui.window import Window,Transcript


def ready_window(qtbot,services):
    window = Window(services)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda: window.hardware_snapshot is not None and window.job_thread is None)
    return window


def test_compact_navigation_and_composer(qtbot,services):
    window = ready_window(qtbot,services)
    window.resize(960,620)
    qtbot.wait(10)
    last = window.nav.visualItemRect(window.nav.item(4))
    assert last.bottom() <= window.nav.viewport().height()
    qtbot.mouseClick(window.nav.viewport(),Qt.MouseButton.LeftButton,pos=last.center())
    assert window.pages.currentIndex()==4
    window.nav.setCurrentRow(0)
    assert window.send_button.isVisible()
    assert window.send_button.geometry().right() < window.send_button.parentWidget().width()
    assert window.composer.height() >= 64
    window.close()


def test_search_and_open_saved_session(qtbot,services,model_file):
    model = services.import_model(model_file)
    alpha,beta = services.new_conversation(model.id),services.new_conversation(model.id)
    alpha['title'],beta['title'] = 'Physics notes','Biology notes'
    for conv in (alpha,beta):
        services.db.put('conversations',conv['id'],conv)
    window = ready_window(qtbot,services)
    window.session_search.setText('BIOLOGY')
    visible = [window.conversations.item(i) for i in range(window.conversations.count())
               if not window.conversations.item(i).isHidden()]
    assert [item.text() for item in visible]==['Biology notes']
    window.nav.setCurrentRow(3)
    window.open_session(visible[0])
    assert window.pages.currentIndex()==0 and window.conversation_id==beta['id']
    assert window.session_title.text()=='Biology notes'
    window.session_search.setText('missing')
    assert window.session_empty.isVisible()
    window.close()


def test_command_search_dispatch(qtbot):
    called = []
    palette = CommandPalette(None,[('Open Models','Ctrl+2',lambda:called.append('models')),
                                   ('Open Settings','Ctrl+5',lambda:called.append('settings'))])
    qtbot.addWidget(palette)
    palette.show()
    palette.search.setText('settings')
    assert palette.results.count()==1
    qtbot.keyClick(palette.search,Qt.Key.Key_Return)
    assert called==['settings'] and not palette.isVisible()


def test_command_no_match_and_keyboard(qtbot):
    palette = CommandPalette(None,[('Open Chat','',lambda:None)])
    qtbot.addWidget(palette)
    palette.show()
    qtbot.waitUntil(palette.isActiveWindow)
    palette.search.setText('not a command')
    qtbot.keyClick(palette.search,Qt.Key.Key_Return)
    assert palette.isVisible() and palette.results.count()==0
    palette.search.clear()
    qtbot.keyClick(palette.search,Qt.Key.Key_Down)
    assert palette.results.hasFocus()
    qtbot.keyClick(palette.results,Qt.Key.Key_Escape)
    assert not palette.isVisible()


def test_theme_saves_without_runtime(qtbot,services):
    window = ready_window(qtbot,services)
    window.theme.setCurrentText('light')
    assert services.config()['theme']=='light'
    assert '#faf9f5' in window.styleSheet()
    assert services.config()['runtime_folder']==''
    window.close()


def test_shortcut_sidebar_and_menu_busy_state(qtbot,services):
    window = ready_window(qtbot,services)
    qtbot.keyClick(window,Qt.Key.Key_B,modifier=Qt.KeyboardModifier.ControlModifier)
    assert window.sidebar.isHidden()
    qtbot.keyClick(window,Qt.Key.Key_B,modifier=Qt.KeyboardModifier.ControlModifier)
    assert not window.sidebar.isHidden()
    def operation(progress,chunk):
        services.cancel.wait(3)
    window.job(operation,lambda _:None,'Test cancellable task')
    assert all(not action.isEnabled() for action in window.busy_actions)
    assert window.stop_button.isVisible()
    window.stop()
    qtbot.waitUntil(lambda:window.job_thread is None)
    assert all(action.isEnabled() for action in window.busy_actions)
    assert not window.stop_button.isVisible()
    window.close()


def test_transcript_preserves_code_and_rejects_raw_html(qtbot):
    transcript = Transcript()
    qtbot.addWidget(transcript)
    transcript.setMarkdown('### InferLM\n\n**Answer**\n\n```python\nprint("hello")\n```\n\n<img src="https://example.com/a.png">')
    assert 'Answer' in transcript.toPlainText()
    assert 'print("hello")' in transcript.toPlainText()
    assert '<img' not in transcript.toHtml()
