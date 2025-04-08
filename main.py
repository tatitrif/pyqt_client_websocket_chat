import json
import logging
import os
import sys
import threading

import requests
from PyQt6 import uic, QtWidgets, QtGui
from websockets.sync import client
from websockets.sync.client import ClientConnection

HOST, PORT = "127.0.0.1", 8089
URL_API = "/api/v1"
CHAT_PATH = URL_API + "/chat/ws"
logger = logging.getLogger(__name__)


# for PyInstaller must be full path
def get_full_path_ui(filename: str):
    try:
        # временный каталог PyInstaller
        base_path = sys._MEIPASS
    except:  # noqa: E722 B001
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "ui", filename)


class Chat(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        # interface from Qt Designer
        self.ui = uic.loadUi(get_full_path_ui("chat.ui"), self)
        self.setWindowIcon(QtGui.QIcon(get_full_path_ui("icon.png")))
        self.setWindowTitle("Chat")

        self.access_token = None
        self.client: ClientConnection = None
        # прописываем сигналы и слоты
        # в данном случае сигналы - это события (clicked),
        # а слоты - это функции, которые нужно выполнить (login, write)
        self.ui.ok.clicked.connect(self.login)
        self.ui.send.clicked.connect(self.write)

    def login(self):
        """авторизация."""
        try:
            # Получение введенных пользователем логина и пароля
            username = self.ui.username.text()
            password = self.ui.password.text()
            if not username or not password:
                self.ui.label_2.setText("Заполните все поля")
            else:
                url = "http://" + HOST + ":" + str(PORT) + "/api/v1/auth/token"
                data = {"username": username, "password": password}
                response = requests.post(url, data=data, timeout=10)
                response_content = json.loads(response.content)
                if response.ok:
                    self.access_token = response_content.get("access_token")

                    self.ui.label_2.clear()
                    # открываем возможность ввода сообщения
                    self.ui.msg_line.setEnabled(True)
                    self.ui.send.setEnabled(True)
                    # блокируем возможность ввода другого никнейма
                    self.ui.username.setEnabled(False)
                    self.ui.password.setEnabled(False)
                    self.ui.ok.setEnabled(False)
                else:
                    detail = response_content.get("detail", "User not found")
                    self.ui.label_2.setText(detail)
        except requests.exceptions.RequestException as err:
            self.ui.label_2.setText("Connection error")
            logger.error(f"Request sending error: {err}")
        except Exception as err:
            logger.error(f"Exception: {err}")

        # стартуем поток, который постоянно будет пытаться получить сообщения
        receive_thread = threading.Thread(target=self.receive)
        receive_thread.start()

    def receive(self):
        """Получение сообщений от других клиентов."""
        try:
            url = f"ws://{HOST}:{PORT}{CHAT_PATH}?token={self.access_token}"
            self.client = client.connect(url)
            with client.connect(url) as websocket:
                while True:
                    self.ui.label_2.clear()
                    # пытаемся получить сообщение
                    response_content = json.loads(websocket.recv(1024))
                    sender = response_content.get("sender")
                    text = response_content.get("text")
                    message = f"{sender}: {text}"
                    # if not message.startswith(self.ui.username.text()):
                    self.ui.messages.append(message)

        except Exception as e:
            logger.warning(f"receive {e}")
            # в случае любой ошибки блочим открытые инпуты
            self.ui.msg_line.setEnabled(False)
            self.ui.send.setEnabled(False)
            # блокируем возможность ввода другого никнейма
            self.ui.username.setEnabled(True)
            self.ui.password.setEnabled(True)
            self.ui.ok.setEnabled(True)

    def write(self):
        """Отправляет сообщение серверу."""
        message = dict(receiver="all", text=self.ui.msg_line.text())
        # отправляем сообщение серверу
        self.client.send(json.dumps(message))
        self.ui.msg_line.clear()


def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
        window = Chat()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")


if __name__ == "__main__":
    main()
