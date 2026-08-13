import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from controllers.main_window_controller import MainWindowController


def main():
    app = QApplication(sys.argv)
    janela = QMainWindow()
    controller = MainWindowController(janela)
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
