import subprocess
import sys
from PySide6.QtCore import Qt
from typer.testing import CliRunner
from inferlm.cli.app import app
from inferlm.gui.window import Window,Composer

def test_cli_help():
    result = CliRunner().invoke(app,["--help"])
    assert result.exit_code==0 and "doctor" in result.stdout and "optimize" in result.stdout

def test_cli_without_qt():
    result = subprocess.run([sys.executable,"-c","from inferlm.cli.app import app;import sys;"
                             "assert not any(x.startswith('PySide6') for x in sys.modules)"],capture_output=True,text=True)
    assert result.returncode==0,result.stderr

def test_gui_navigation(qtbot,services):
    window = Window(services)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(lambda:window.job_thread is None,timeout=10000)
    assert window.pages.count()==5
    for index in range(5):
        window.nav.setCurrentRow(index)
        assert window.pages.currentIndex()==index
    window.resize(1280,720)
    assert window.isVisible()
    window.close()

def test_composer_keyboard(qtbot):
    composer = Composer()
    qtbot.addWidget(composer)
    with qtbot.waitSignal(composer.send):
        qtbot.keyClick(composer,Qt.Key.Key_Return)
    qtbot.keyClicks(composer,"hello")
    qtbot.keyClick(composer,Qt.Key.Key_Return,modifier=Qt.KeyboardModifier.ShiftModifier)
    assert composer.toPlainText()=="hello\n"

