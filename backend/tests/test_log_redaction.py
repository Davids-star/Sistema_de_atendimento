import logging

from app.core.logging import RedactingFormatter, redact

TOKEN = "9876543210:AAH-abcdefghijklmnopqrstuvwxyz012345"


def test_tokens_are_hidden_in_every_form():
    assert TOKEN not in redact(f"POST /bot{TOKEN}/getUpdates HTTP/1.1")
    assert TOKEN not in redact(f"token={TOKEN} ok") and TOKEN not in redact(f"x {TOKEN}, y")
    assert "<token oculto>" in redact(f"/bot{TOKEN}/sendMessage")


def test_normal_text_is_untouched():
    for text in ["agendado 12:30 e 09:45", "fone 5511999998888", "2026-10-29T12:30:00", "tg:123456:7", "10:30:45"]:
        assert redact(text) == text


def test_the_final_log_line_including_tracebacks_is_clean():
    try:
        raise ConnectionError(f"Max retries exceeded with url: /bot{TOKEN}/getUpdates")
    except ConnectionError:
        import sys
        record = logging.LogRecord("x", logging.ERROR, "f.py", 1, "falhou ao falar com o Telegram", None, sys.exc_info())
    out = RedactingFormatter("%(message)s").format(record)
    assert TOKEN not in out and "<token oculto>" in out and "falhou ao falar" in out


def test_urllib3_is_quiet_by_default_so_it_does_not_print_urls(monkeypatch):
    import logging.config
    from app.core.logging import setup_logging
    setup_logging()
    assert logging.getLogger("urllib3").level >= logging.WARNING
