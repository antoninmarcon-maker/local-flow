"""Self-check de la machine a etats fn avec des CGEvents synthetiques.

Aucune permission macOS requise : le callback est appele directement, sans
tap reel (creer un CGEvent est libre, seuls le tap et le post sont proteges).
Usage : uv run python tests/test_fn_listener.py
"""

import Quartz

from localflow.app import FN_KEYCODE, FnListener


def make_fn_event(down: bool) -> object:
    event = Quartz.CGEventCreateKeyboardEvent(None, FN_KEYCODE, True)
    Quartz.CGEventSetType(event, Quartz.kCGEventFlagsChanged)
    Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskSecondaryFn if down else 0)
    return event


def make_keydown(keycode: int) -> object:
    return Quartz.CGEventCreateKeyboardEvent(None, keycode, True)


def make_listener(log: list) -> FnListener:
    return FnListener(
        on_press=lambda: log.append("press"),
        on_release=lambda: log.append("release"),
        on_cancel=lambda: log.append("cancel"),
    )


def send(listener: FnListener, event: object) -> None:
    listener._callback(None, Quartz.CGEventGetType(event), event, None)


def test_hold_release() -> None:
    log: list = []
    listener = make_listener(log)
    send(listener, make_fn_event(True))
    send(listener, make_fn_event(False))
    assert log == ["press", "release"], log


def test_combo_annule() -> None:
    log: list = []
    listener = make_listener(log)
    send(listener, make_fn_event(True))
    send(listener, make_keydown(126))  # fleche haut pendant l'enregistrement
    send(listener, make_fn_event(False))  # la release ne doit rien declencher
    assert log == ["press", "cancel"], log


def test_keydown_sans_fn_ignore() -> None:
    log: list = []
    listener = make_listener(log)
    send(listener, make_keydown(0))
    assert log == [], log


def test_autres_modificateurs_ignores() -> None:
    log: list = []
    listener = make_listener(log)
    event = Quartz.CGEventCreateKeyboardEvent(None, 58, True)  # kVK_Option
    Quartz.CGEventSetType(event, Quartz.kCGEventFlagsChanged)
    Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskAlternate)
    send(listener, event)
    assert log == [], log


if __name__ == "__main__":
    test_hold_release()
    test_combo_annule()
    test_keydown_sans_fn_ignore()
    test_autres_modificateurs_ignores()
    print("OK : machine a etats fn (press/release, annulation combo, filtres)")
