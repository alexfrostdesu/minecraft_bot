import requests
import os
import time
import typing as t
from dataclasses import dataclass, field

TELEGRAM_API = "https://api.telegram.org/"
MINECRAFT_API = "https://api.mcsrvstat.us/2/"


@dataclass
class TelegramMessage:
    message: dict | None = field(default_factory=dict)
    edited_message: dict | None = field(default_factory=dict)
    my_chat_member: dict | None = field(default_factory=dict)
    commands: set | None = field(default_factory=set)
    update_id: int | None = None
    text: str | None = None
    is_edited: bool | None = isinstance(edited_message, dict)
    is_from_group: bool | None = isinstance(my_chat_member, dict)

    def get_command(self, start: int, end: int) -> str:
        return self.text[start:end]

    def erase_command(self, start: int, end: int) -> str:
        return self.text[:start] + self.text[end + 1:]

    def __post_init__(self):
        self.text = self.message.get("text") or self.edited_message.get("text")
        if self.text:
            commands_indexes = [
                dict(
                    start=e["offset"],
                    end=e["offset"] + e["length"]
                )
                for e in self.message.get("entities", []) if e["type"] == "bot_command"]
            for index in sorted(commands_indexes, key=lambda x: x.get("start"), reverse=True):
                self.commands.add(self.get_command(**index))
                self.text = self.erase_command(**index)

    @property
    def offset(self) -> int:
        return self.update_id if None else self.update_id + 1

    @property
    def from_id(self) -> int:
        return (
                self.message.get("from", {}).get("id") or
                self.edited_message.get("from", {}).get("id") or
                self.my_chat_member.get("from", {}).get("id")
        )

    @property
    def chat_id(self) -> int:
        return (
                self.message.get("chat", {}).get("id") or
                self.edited_message.get("chat", {}).get("id") or
                self.my_chat_member.get("chat", {}).get("id")
        )


    @property
    def message_id(self) -> int:
        return self.message.get("message_id") or self.edited_message.get("message_id")


class BotHandler:
    def __init__(self, bot_token: str, server_ip: str):
        self.telegram_url = TELEGRAM_API + bot_token + "/"
        self.minecraft_url = MINECRAFT_API + server_ip
        self.current_offset = None
        self.last_message = {}
        self.available_commands = {
            "/check_status": self.check_status
        }

    def check_status(self) -> str:
        res = requests.get(self.minecraft_url)
        server_data = res.json()
        online = "✅" if server_data["online"] else "❌"
        text = f"""
        Server {server_data["motd"]["clean"]} @ {server_data["ip"]}:
         -online {online}
         -players {server_data["players"]["list"]}
        """
        return text

    def update_last_message(self, chat_id: int, message_data: dict):
        if message_data["ok"]:
            self.last_message[chat_id] = TelegramMessage(
                message=message_data["result"]
            )

    def get_messages(self) -> requests.Response:
        return requests.get(
            self.telegram_url + "getUpdates",
            params=dict(
                allowed_updates=["message", ],
                offset=self.current_offset
            )
        )

    @staticmethod
    def unpack_messages(messages: dict) -> t.List[TelegramMessage] | None:
        if messages["ok"]:
            return [TelegramMessage(**ms) for ms in messages["result"]]

    def send_message(self, text: str, chat_id: int, from_id: int, silent: bool = False):
        message = requests.post(
            self.telegram_url + "sendMessage",
            {"text": text,
             "chat_id": chat_id,
             "from": from_id,
             "parse_mode": "Markdown",
             "reply_markup": None,
             "disable_notification": silent
             }
        )
        if message.status_code == 200:
            self.update_last_message(chat_id, message.json())

    def edit_message(self, text: str, message_id: int, chat_id: int):
        message = requests.post(
            self.telegram_url + "editMessageText",
            {"text": text,
             "message_id": message_id,
             "chat_id": chat_id,
             "parse_mode": "Markdown",
             "reply_markup": None
             }
        )
        if message.status_code == 200:
            self.update_last_message(chat_id, message.json())

    def delete_message(self, message_id: int, chat_id: int):
        message = requests.post(
            self.telegram_url + "deleteMessage",
            {"message_id": message_id,
             "chat_id": chat_id,
             "parse_mode": "Markdown",
             "reply_markup": None
             }
        )
        if message.status_code == 200:
            self.last_message.pop(chat_id)

    def handle_commands(self, message: TelegramMessage):
        for comm in message.commands:
            if comm in self.available_commands:
                text = self.available_commands[comm]()
                self.send_message(text, message.chat_id, message.from_id, silent=message.is_from_group)

    def run(self):
        while True:
            messages_response = self.get_messages()
            print(messages_response, flush=True)
            if messages_response.status_code == 200:
                print(messages_response.json(), flush=True)
                telegram_messages = self.unpack_messages(messages_response.json())
                for message in telegram_messages:
                    self.handle_commands(message)
                    self.current_offset = message.offset

            time.sleep(1)


handler = BotHandler(
    bot_token=os.getenv("BOT_TOKEN"),
    server_ip=os.getenv("SERVER_IP")
)


if __name__ == "__main__":
    handler.run()
