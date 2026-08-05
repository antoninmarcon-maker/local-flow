"""Interface : icone barre de menus + panneau flottant non-activant.

Le panneau affiche la transcription en direct pendant la dictee puis les
boutons d'action (Coller / Corriger / traductions / Pro / Amical). Style
NSWindowStyleMaskNonactivatingPanel : il ne vole JAMAIS le focus de l'app
cible — condition pour que le collage parte au bon endroit.

Regle de threading : tout AppKit passe par le thread principal. Les methodes
publiques (appelees depuis le worker ou l'apercu) postent via AppHelper.callAfter.
"""

import objc
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSControlStateValueOff,
    NSControlStateValueOn,
    NSFloatingWindowLevel,
    NSFont,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPanel,
    NSScreen,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialPopover,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

from localflow.config import TRANSLATE_LANGS, Settings

PANEL_W = 600
PANEL_H = 150
PANEL_BOTTOM = 120  # au-dessus du Dock, sous le champ de saisie de la plupart des apps

TOGGLES = [
    ("live_preview", "Apercu en direct pendant la dictee"),
    ("preview_before_paste", "Valider avant de coller"),
    ("auto_register", "Ton adapte a l'app active"),
    ("read_context", "Lire la conversation pour le ton"),
    ("habits_enabled", "Apprendre mes habitudes d'ecriture"),
]


class _UIDelegate(NSObject):
    """Cible objc des menus, boutons et timers. Route vers l'objet UI python."""

    def initWithUI_(self, ui):
        self = objc.super(_UIDelegate, self).init()
        if self is None:
            return None
        self.ui = ui
        return self

    def menuToggle_(self, item):
        key = str(item.representedObject())
        value = not getattr(self.ui.settings, key)
        setattr(self.ui.settings, key, value)
        self.ui.settings.save()
        item.setState_(NSControlStateValueOn if value else NSControlStateValueOff)

    def menuLang_(self, item):
        code = str(item.representedObject())
        self.ui.settings.toggle_lang(code)
        item.setState_(NSControlStateValueOn if code in self.ui.settings.translate_langs
                       else NSControlStateValueOff)

    def buttonAction_(self, sender):
        ident = str(sender.identifier())
        if ident == "paste":
            self.ui.app.request_paste_last()
        elif ident.startswith("translate:"):
            self.ui.app.request_action("translate", ident.split(":", 1)[1])
        else:
            self.ui.app.request_action(ident)

    def hideTimer_(self, _timer):
        self.ui._do_hide()

    def quitApp_(self, _item):
        NSApplication.sharedApplication().terminate_(None)


def _label(frame, size, color=None, bold=False):
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    field.setFont_(font)
    if color is not None:
        field.setTextColor_(color)
    field.setLineBreakMode_(NSLineBreakByTruncatingTail)
    return field


class UI:
    def __init__(self, settings: Settings, app) -> None:
        self.settings = settings
        self.app = app  # localflow.app.App (request_action, request_paste_last)
        self._delegate = None
        self._status_item = None
        self._status_menu_item = None
        self._panel = None
        self._status_label = None
        self._text_label = None
        self._buttons: list = []
        self._hide_timer = None
        self._full_text = ""

    # ------------------------------------------------------------------ setup

    def setup(self) -> None:
        """A appeler sur le thread principal, avant runEventLoop."""
        self._delegate = _UIDelegate.alloc().initWithUI_(self)
        self._setup_status_item()
        self._setup_panel()

    def _setup_status_item(self) -> None:
        bar = NSStatusBar.systemStatusBar()
        self._status_item = bar.statusItemWithLength_(NSVariableStatusItemLength)
        self._status_item.button().setTitle_("🎙")
        menu = NSMenu.alloc().init()
        self._status_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Demarrage…", None, "")
        menu.addItem_(self._status_menu_item)
        menu.addItem_(NSMenuItem.separatorItem())
        for key, title in TOGGLES:
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                title, "menuToggle:", "")
            item.setTarget_(self._delegate)
            item.setRepresentedObject_(key)
            item.setState_(NSControlStateValueOn if getattr(self.settings, key)
                           else NSControlStateValueOff)
            menu.addItem_(item)
        langs_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Langues de traduction", None, "")
        langs_menu = NSMenu.alloc().init()
        for code, name in TRANSLATE_LANGS.items():
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                name, "menuLang:", "")
            item.setTarget_(self._delegate)
            item.setRepresentedObject_(code)
            item.setState_(NSControlStateValueOn if code in self.settings.translate_langs
                           else NSControlStateValueOff)
            langs_menu.addItem_(item)
        langs_item.setSubmenu_(langs_menu)
        menu.addItem_(langs_item)
        menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quitter LocalFlow", "quitApp:", "q")
        quit_item.setTarget_(self._delegate)
        menu.addItem_(quit_item)
        self._status_item.setMenu_(menu)

    def _setup_panel(self) -> None:
        rect = self._panel_rect()
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskBorderless | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        panel.setBecomesKeyOnlyIfNeeded_(True)
        panel.setHidesOnDeactivate_(False)
        panel.setOpaque_(False)
        panel.setBackgroundColor_(NSColor.clearColor())
        # fond : effet natif translucide arrondi (pas de CGColor : PyObjC n'en
        # type pas le pointeur et l'affectation echoue silencieusement)
        effect = NSVisualEffectView.alloc().initWithFrame_(
            NSMakeRect(0, 0, PANEL_W, PANEL_H))
        effect.setMaterial_(NSVisualEffectMaterialPopover)
        effect.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        effect.setState_(NSVisualEffectStateActive)
        effect.setWantsLayer_(True)
        effect.layer().setCornerRadius_(14.0)
        effect.layer().setMasksToBounds_(True)
        panel.setContentView_(effect)
        content = panel.contentView()
        self._status_label = _label(
            NSMakeRect(20, PANEL_H - 32, PANEL_W - 40, 18), 11,
            color=NSColor.secondaryLabelColor())
        content.addSubview_(self._status_label)
        self._text_label = _label(NSMakeRect(20, 52, PANEL_W - 40, PANEL_H - 90), 13)
        self._text_label.setMaximumNumberOfLines_(3)
        self._text_label.cell().setTruncatesLastVisibleLine_(True)
        content.addSubview_(self._text_label)
        self._panel = panel

    def _panel_rect(self):
        screen = NSScreen.mainScreen()
        frame = screen.visibleFrame() if screen else NSMakeRect(0, 0, 1440, 900)
        x = frame.origin.x + (frame.size.width - PANEL_W) / 2
        y = frame.origin.y + PANEL_BOTTOM
        return NSMakeRect(x, y, PANEL_W, PANEL_H)

    # ----------------------------------------------------------- etats du panneau
    # Methodes publiques thread-safe : elles postent sur le thread principal.

    def show_recording(self) -> None:
        AppHelper.callAfter(self._do_show, "● J'ecoute — relacher pour transcrire", "", [])

    def show_preview(self, text: str) -> None:
        AppHelper.callAfter(self._do_preview, text)

    def show_working(self, message: str) -> None:
        AppHelper.callAfter(self._do_show, message, self._full_text, [])

    def show_final(self, text: str, pasted: bool, note: str | None = None) -> None:
        AppHelper.callAfter(self._do_final, text, pasted, note)

    def show_message(self, message: str, autohide: float = 5.0) -> None:
        AppHelper.callAfter(self._do_show, message, "", [], autohide)

    def hide_panel(self) -> None:
        AppHelper.callAfter(self._do_hide)

    def set_status(self, message: str) -> None:
        AppHelper.callAfter(self._do_set_status, message)

    # ------------------------------------------------------- implementations (main)

    def _cancel_timer(self) -> None:
        if self._hide_timer is not None:
            self._hide_timer.invalidate()
            self._hide_timer = None

    def _schedule_hide(self, delay: float) -> None:
        self._cancel_timer()
        self._hide_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            delay, self._delegate, "hideTimer:", None, False)

    def _do_set_status(self, message: str) -> None:
        if self._status_menu_item is not None:
            self._status_menu_item.setTitle_(message)
        if self._status_item is not None:
            self._status_item.button().setToolTip_(message)

    def _clear_buttons(self) -> None:
        for b in self._buttons:
            b.removeFromSuperview()
        self._buttons = []

    def _make_buttons(self, specs: list[tuple[str, str]]) -> None:
        """specs : [(libelle, identifiant)] -> rangee de boutons en bas du panneau."""
        self._clear_buttons()
        content = self._panel.contentView()
        x = 16
        for title, ident in specs:
            b = NSButton.alloc().initWithFrame_(NSMakeRect(x, 10, 10, 30))
            b.setTitle_(title)
            b.setBezelStyle_(1)  # NSBezelStyleRounded
            b.setIdentifier_(ident)
            b.setTarget_(self._delegate)
            b.setAction_("buttonAction:")
            b.sizeToFit()
            frame = b.frame()
            frame.origin.x = x
            frame.origin.y = 10
            frame.size.height = max(frame.size.height, 28)
            b.setFrame_(frame)
            if x + frame.size.width > PANEL_W - 16:
                break  # pas de deuxieme rangee : on tronque plutot que deborder
            content.addSubview_(b)
            self._buttons.append(b)
            x += frame.size.width + 8

    def _do_show(self, status: str, text: str, button_specs: list,
                 autohide: float | None = None) -> None:
        self._cancel_timer()
        self._full_text = text
        self._status_label.setStringValue_(status)
        self._text_label.setStringValue_(text)
        self._make_buttons(button_specs)
        self._panel.setFrame_display_(self._panel_rect(), True)
        self._panel.orderFrontRegardless()
        if autohide:
            self._schedule_hide(autohide)

    def _do_preview(self, text: str) -> None:
        # pas de reordering ni reset du timer : seul le texte bouge
        self._full_text = text
        self._text_label.setStringValue_(text)

    def _do_final(self, text: str, pasted: bool, note: str | None) -> None:
        specs: list[tuple[str, str]] = []
        if not pasted:
            specs.append(("Coller", "paste"))
        specs.append(("Corriger", "correct"))
        for code in self.settings.translate_langs:
            specs.append((f"→ {code.upper()}", f"translate:{code}"))
        specs.append(("Pro", "pro"))
        specs.append(("Amical", "friendly"))
        if note:
            status = note
        elif pasted:
            status = "Colle ✓ — transformer :"
        else:
            status = "Preview — coller ou transformer :"
        self._do_show(status, text, specs, autohide=10.0 if pasted else 30.0)

    def _do_hide(self) -> None:
        self._cancel_timer()
        if self._panel is not None:
            self._panel.orderOut_(None)
