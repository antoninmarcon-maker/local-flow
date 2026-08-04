"""Detection de la touche push-to-talk (fn via event tap Quartz, autres via pynput)."""

import Quartz
from pynput import keyboard

FN_KEYCODE = 63  # kVK_Function

KEYS = {
    "fn": None,  # geree par FnListener (event tap Quartz), pas par pynput
    "alt_r": keyboard.Key.alt_r,
    "cmd_r": keyboard.Key.cmd_r,
    "ctrl_r": keyboard.Key.ctrl_r,
    "f8": keyboard.Key.f8,
    "f13": keyboard.Key.f13,
}


class FnListener:
    """Touche fn via un event tap Quartz : pynput ne la voit pas sur macOS
    (elle n'emet que des flagsChanged, keycode 63). fn servant aussi aux combos
    systeme (fn+fleches...), l'appui d'une autre touche pendant l'enregistrement
    annule la dictee au lieu de coller du texte fantome.

    ponytail: nos propres frappes synthetiques (Cmd+V du collage) redescendent
    par ce meme tap. Sans le garde is_pasting, le collage de la dictee n
    annulait la dictee n+1 en cours d'enregistrement (auto-sabotage)."""

    def __init__(self, on_press, on_release, on_cancel, is_pasting=None) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.on_cancel = on_cancel
        self.is_pasting = is_pasting or (lambda: False)
        self._fn_down = False
        self._tap = None

    def _callback(self, _proxy: object, type_: int, event: object, _refcon: object) -> object:
        if type_ == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(self._tap, True)
        elif type_ == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
            if keycode == FN_KEYCODE:
                down = bool(Quartz.CGEventGetFlags(event) & Quartz.kCGEventFlagMaskSecondaryFn)
                if down and not self._fn_down:
                    self._fn_down = True
                    self.on_press()
                elif not down and self._fn_down:
                    self._fn_down = False
                    self.on_release()
        elif type_ == Quartz.kCGEventKeyDown and self._fn_down:
            if self.is_pasting():
                return event  # frappe synthetique de notre collage, pas l'utilisateur
            self._fn_down = False  # la release de fn qui suivra sera ignoree
            self.on_cancel()
        return event

    def prepare(self) -> None:
        """Cree le tap avant le chargement du modele : echec de permission = sortie
        immediate, sans charger 2 GB pour rien."""
        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionListenOnly,
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
            | Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
            self._callback,
            None,
        )
        if self._tap is None:
            raise PermissionError(
                "Impossible d'ecouter le clavier. Ajouter votre terminal dans "
                "Reglages Systeme > Confidentialite et securite > Surveillance de "
                "l'entree, relancer le terminal, puis reessayer."
            )

    def attach_to_current_runloop(self) -> None:
        """Branche le tap sur le run loop courant sans le faire tourner :
        utilise quand NSApplication possede deja le run loop principal."""
        source = Quartz.CFMachPortCreateRunLoopSource(None, self._tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self._tap, True)

    def run(self) -> None:
        """Mode terminal (--no-ui) : le tap possede le run loop et bloque."""
        self.attach_to_current_runloop()
        Quartz.CFRunLoopRun()
