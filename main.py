import logging
import os
import sys

from PySide6.QtWidgets import QApplication, QMainWindow

from controllers.main_window_controller import MainWindowController
from models.config_manager import ConfigManager

PASTA_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
logger = logging.getLogger("smartgrid")


def configurar_logging():
    """Grava os logs em logs/smartgrid.log com data/hora e severidade."""
    os.makedirs(PASTA_LOGS, exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(PASTA_LOGS, "smartgrid.log"),
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
    )


def main():
    configurar_logging()
    logger.info("Aplicação iniciada.")
    ConfigManager.carregar()

    app = QApplication(sys.argv)
    janela = QMainWindow()
    controller = MainWindowController(janela)
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
