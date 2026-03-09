from types import SimpleNamespace

import pytest

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram import TelegramChannel
from nanobot.config.schema import TelegramConfig


class _FakeHTTPXRequest:
    instances: list["_FakeHTTPXRequest"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.__class__.instances.append(self)

    @classmethod
    def clear(cls) -> None:
        cls.instances.clear()


class _FakeUpdater:
    def __init__(self, on_start_polling) -> None:
        self._on_start_polling = on_start_polling

    async def start_polling(self, **kwargs) -> None:
        self._on_start_polling()


class _FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.file = None

    async def get_me(self):
        return SimpleNamespace(username="nanobot_test")

    async def set_my_commands(self, commands) -> None:
        self.commands = commands

    async def send_message(self, **kwargs) -> None:
        self.sent_messages.append(kwargs)

    async def get_file(self, _file_id):
        return self.file


class _FakeApp:
    def __init__(self, on_start_polling) -> None:
        self.bot = _FakeBot()
        self.updater = _FakeUpdater(on_start_polling)
        self.handlers = []
        self.error_handlers = []

    def add_error_handler(self, handler) -> None:
        self.error_handlers.append(handler)

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        pass


class _FakeBuilder:
    def __init__(self, app: _FakeApp) -> None:
        self.app = app
        self.token_value = None
        self.request_value = None
        self.get_updates_request_value = None

    def token(self, token: str):
        self.token_value = token
        return self

    def request(self, request):
        self.request_value = request
        return self

    def get_updates_request(self, request):
        self.get_updates_request_value = request
        return self

    def proxy(self, _proxy):
        raise AssertionError("builder.proxy should not be called when request is set")

    def get_updates_proxy(self, _proxy):
        raise AssertionError("builder.get_updates_proxy should not be called when request is set")

    def build(self):
        return self.app


@pytest.mark.asyncio
async def test_start_creates_separate_pools_with_proxy(monkeypatch) -> None:
    _FakeHTTPXRequest.clear()
    config = TelegramConfig(
        enabled=True,
        token="123:abc",
        allow_from=["*"],
        proxy="http://127.0.0.1:7890",
    )
    bus = MessageBus()
    channel = TelegramChannel(config, bus)
    app = _FakeApp(lambda: setattr(channel, "_running", False))
    builder = _FakeBuilder(app)

    monkeypatch.setattr("nanobot.channels.telegram.HTTPXRequest", _FakeHTTPXRequest)
    monkeypatch.setattr(
        "nanobot.channels.telegram.Application",
        SimpleNamespace(builder=lambda: builder),
    )

    await channel.start()

    assert len(_FakeHTTPXRequest.instances) == 2
    api_req, poll_req = _FakeHTTPXRequest.instances
    assert api_req.kwargs["proxy"] == config.proxy
    assert poll_req.kwargs["proxy"] == config.proxy
    assert api_req.kwargs["connection_pool_size"] == 32
    assert poll_req.kwargs["connection_pool_size"] == 4
    assert builder.request_value is api_req
    assert builder.get_updates_request_value is poll_req


@pytest.mark.asyncio
async def test_start_respects_custom_pool_config(monkeypatch) -> None:
    _FakeHTTPXRequest.clear()
    config = TelegramConfig(
        enabled=True,
        token="123:abc",
        allow_from=["*"],
        connection_pool_size=32,
        pool_timeout=10.0,
    )
    bus = MessageBus()
    channel = TelegramChannel(config, bus)
    app = _FakeApp(lambda: setattr(channel, "_running", False))
    builder = _FakeBuilder(app)

    monkeypatch.setattr("nanobot.channels.telegram.HTTPXRequest", _FakeHTTPXRequest)
    monkeypatch.setattr(
        "nanobot.channels.telegram.Application",
        SimpleNamespace(builder=lambda: builder),
    )

    await channel.start()

    api_req = _FakeHTTPXRequest.instances[0]
    poll_req = _FakeHTTPXRequest.instances[1]
    assert api_req.kwargs["connection_pool_size"] == 32
    assert api_req.kwargs["pool_timeout"] == 10.0
    assert poll_req.kwargs["pool_timeout"] == 10.0


@pytest.mark.asyncio
async def test_send_text_retries_on_timeout() -> None:
    """_send_text retries on TimedOut before succeeding."""
    from telegram.error import TimedOut

    channel = TelegramChannel(
        TelegramConfig(enabled=True, token="123:abc", allow_from=["*"]),
        MessageBus(),
    )
    channel._app = _FakeApp(lambda: None)

    call_count = 0
    original_send = channel._app.bot.send_message

    async def flaky_send(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimedOut()
        return await original_send(**kwargs)

    channel._app.bot.send_message = flaky_send

    import nanobot.channels.telegram as tg_mod
    orig_delay = tg_mod._SEND_RETRY_BASE_DELAY
    tg_mod._SEND_RETRY_BASE_DELAY = 0.01
    try:
        await channel._send_text(123, "hello", None, {})
    finally:
        tg_mod._SEND_RETRY_BASE_DELAY = orig_delay

    assert call_count == 3
    assert len(channel._app.bot.sent_messages) == 1


@pytest.mark.asyncio
async def test_send_text_gives_up_after_max_retries() -> None:
    """_send_text raises TimedOut after exhausting all retries."""
    from telegram.error import TimedOut

    channel = TelegramChannel(
        TelegramConfig(enabled=True, token="123:abc", allow_from=["*"]),
        MessageBus(),
    )
    channel._app = _FakeApp(lambda: None)

    async def always_timeout(**kwargs):
        raise TimedOut()

    channel._app.bot.send_message = always_timeout

    import nanobot.channels.telegram as tg_mod
    orig_delay = tg_mod._SEND_RETRY_BASE_DELAY
    tg_mod._SEND_RETRY_BASE_DELAY = 0.01
    try:
        await channel._send_text(123, "hello", None, {})
    finally:
        tg_mod._SEND_RETRY_BASE_DELAY = orig_delay

    assert channel._app.bot.sent_messages == []


def test_derive_topic_session_key_uses_thread_id() -> None:
    message = SimpleNamespace(
        chat=SimpleNamespace(type="supergroup"),
        chat_id=-100123,
        message_thread_id=42,
    )

    assert TelegramChannel._derive_topic_session_key(message) == "telegram:-100123:topic:42"


def test_get_extension_falls_back_to_original_filename() -> None:
    channel = TelegramChannel(TelegramConfig(), MessageBus())

    assert channel._get_extension("file", None, "report.pdf") == ".pdf"
    assert channel._get_extension("file", None, "archive.tar.gz") == ".tar.gz"


def test_is_allowed_accepts_legacy_telegram_id_username_formats() -> None:
    channel = TelegramChannel(TelegramConfig(allow_from=["12345", "alice", "67890|bob"]), MessageBus())

    assert channel.is_allowed("12345|carol") is True
    assert channel.is_allowed("99999|alice") is True
    assert channel.is_allowed("67890|bob") is True


def test_is_allowed_rejects_invalid_legacy_telegram_sender_shapes() -> None:
    channel = TelegramChannel(TelegramConfig(allow_from=["alice"]), MessageBus())

    assert channel.is_allowed("attacker|alice|extra") is False
    assert channel.is_allowed("not-a-number|alice") is False


@pytest.mark.asyncio
async def test_send_progress_keeps_message_in_topic() -> None:
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp(lambda: None)

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="hello",
            metadata={"_progress": True, "message_thread_id": 42},
        )
    )

    assert channel._app.bot.sent_messages[0]["message_thread_id"] == 42


@pytest.mark.asyncio
async def test_send_reply_infers_topic_from_message_id_cache() -> None:
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"], reply_to_message=True)
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp(lambda: None)
    channel._message_threads[("123", 10)] = 42

    await channel.send(
        OutboundMessage(
            channel="telegram",
            chat_id="123",
            content="hello",
            metadata={"message_id": 10},
        )
    )

    assert channel._app.bot.sent_messages[0]["message_thread_id"] == 42
    assert channel._app.bot.sent_messages[0]["reply_parameters"].message_id == 10


@pytest.mark.asyncio
async def test_on_message_uses_file_unique_id_for_downloaded_media(monkeypatch, tmp_path) -> None:
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp(lambda: None)

    downloaded: dict[str, str] = {}

    class _FakeDownloadedFile:
        async def download_to_drive(self, path: str) -> None:
            downloaded["path"] = path

    channel._app.bot.file = _FakeDownloadedFile()

    captured: dict[str, object] = {}

    async def _capture_message(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(channel, "_handle_message", _capture_message)
    monkeypatch.setattr(channel, "_start_typing", lambda _chat_id: None)
    monkeypatch.setattr("nanobot.channels.telegram.get_media_dir", lambda _name=None: tmp_path)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=123, username="alice", first_name="Alice"),
        message=SimpleNamespace(
            message_id=1,
            chat=SimpleNamespace(type="private", is_forum=False),
            chat_id=456,
            text=None,
            caption=None,
            photo=[
                SimpleNamespace(
                    file_id="file-id-that-should-not-be-used",
                    file_unique_id="stable-unique-id",
                    mime_type="image/jpeg",
                    file_name=None,
                )
            ],
            voice=None,
            audio=None,
            document=None,
            media_group_id=None,
            message_thread_id=None,
        ),
    )

    await channel._on_message(update, None)

    assert downloaded["path"].endswith("stable-unique-id.jpg")
    assert captured["media"] == [str(tmp_path / "stable-unique-id.jpg")]
