# -*- coding: UTF-8 -*-
"""
WhatsApp Unified — plugin global.
Registra o executável e painel de configurações.
"""

import globalPluginHandler
import appModuleHandler
import addonHandler
import config
import gui
import wx
from gui.settingsDialogs import SettingsPanel, NVDASettingsDialog
import api
import controlTypes
import speech
import ui
import winUser

addonHandler.initTranslation()

CONFIG_SECTION = "whatsAppUnified"
SPEC = {
    "filterPhoneNumbers":   "boolean(default=True)",
    "filterChatList":       "boolean(default=False)",
    "filterMessageList":    "boolean(default=True)",
    "filterUsageHints":     "boolean(default=True)",
    "filterTalvez":         "boolean(default=True)",
    "autoFocusMode":        "boolean(default=True)",
    "scope":                "string(default='desktop')",
}

SCOPE_CHOICES = [
    ("desktop", _("Apenas aplicativo (Desktop)")),
    ("web",     _("Apenas WhatsApp Web (navegador)")),
    ("both",    _("Ambos")),
]


class WhatsAppUnifiedSettings(SettingsPanel):
    title = _("WhatsApp Unificado")

    def makeSettings(self, settingsSizer):
        helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
        c = config.conf.get(CONFIG_SECTION, {})

        # Escopo
        scope_labels = [label for _, label in SCOPE_CHOICES]
        self.scope = helper.addLabeledControl(
            _("Aplicar para:"),
            wx.Choice,
            choices=scope_labels,
        )
        current_scope = c.get("scope", "desktop")
        scope_keys = [key for key, _ in SCOPE_CHOICES]
        idx = scope_keys.index(current_scope) if current_scope in scope_keys else 0
        self.scope.SetSelection(idx)

        self.filterPhoneNumbers = helper.addItem(wx.CheckBox(
            self, label=_("Filtrar números de telefone nas mensagens")))
        self.filterPhoneNumbers.SetValue(bool(c.get("filterMessageList", True)))

        self.filterChatList = helper.addItem(wx.CheckBox(
            self, label=_("Filtrar números de telefone na lista de conversas")))
        self.filterChatList.SetValue(bool(c.get("filterChatList", False)))

        self.filterUsageHints = helper.addItem(wx.CheckBox(
            self, label=_("Silenciar dicas de uso ('Para mais opções...')")))
        self.filterUsageHints.SetValue(bool(c.get("filterUsageHints", True)))

        self.filterTalvez = helper.addItem(wx.CheckBox(
            self, label=_("Remover 'Talvez' antes de nomes de contato")))
        self.filterTalvez.SetValue(bool(c.get("filterTalvez", True)))

        self.autoFocusMode = helper.addItem(wx.CheckBox(
            self, label=_("Manter modo foco automaticamente (recomendado)")))
        self.autoFocusMode.SetValue(bool(c.get("autoFocusMode", True)))

    def onSave(self):
        c = config.conf[CONFIG_SECTION]
        scope_keys = [key for key, _ in SCOPE_CHOICES]
        c["scope"]           = scope_keys[self.scope.GetSelection()]
        c["filterMessageList"] = self.filterPhoneNumbers.IsChecked()
        c["filterChatList"]    = self.filterChatList.IsChecked()
        c["filterUsageHints"]  = self.filterUsageHints.IsChecked()
        c["filterTalvez"]      = self.filterTalvez.IsChecked()
        c["autoFocusMode"]     = self.autoFocusMode.IsChecked()
        config.conf.save()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    scriptCategory = _("WhatsApp Unificado")

    def __init__(self):
        super().__init__()
        config.conf.spec[CONFIG_SECTION] = SPEC
        if CONFIG_SECTION not in config.conf:
            config.conf[CONFIG_SECTION] = {}
        appModuleHandler.registerExecutableWithAppModule("WhatsApp", "whatsapp_root")
        appModuleHandler.registerExecutableWithAppModule("WhatsApp.Root", "whatsapp_root")
        NVDASettingsDialog.categoryClasses.append(WhatsAppUnifiedSettings)

    def terminate(self):
        appModuleHandler.unregisterExecutable("WhatsApp")
        appModuleHandler.unregisterExecutable("WhatsApp.Root")
        if WhatsAppUnifiedSettings in NVDASettingsDialog.categoryClasses:
            NVDASettingsDialog.categoryClasses.remove(WhatsAppUnifiedSettings)
        super().terminate()

    # ── WhatsApp Web — foco e live region sem delay ───────────────────────────

    _BROWSER_EXES = frozenset({
        "chrome", "msedge", "firefox", "opera", "brave", "vivaldi", "iexplore"
    })

    # Cache: evita traversal pesado no event_liveRegionChange
    _in_whatsapp_web = False

    def _check_whatsapp_web(self, obj):
        """Verifica se obj está num browser com WhatsApp Web aberto.
        Usa título da janela em primeiro plano — mais rápido que traversal de árvore."""
        scope = config.conf.get(CONFIG_SECTION, {}).get("scope", "desktop")
        if scope == "desktop":
            return False
        try:
            appName = obj.appModule.appName.lower().replace(".exe", "")
            if appName not in self._BROWSER_EXES:
                return False
            hwnd = winUser.getForegroundWindow()
            title = winUser.getWindowText(hwnd).lower()
            return "whatsapp" in title
        except Exception:
            return False

    def event_gainFocus(self, obj, nextHandler):
        """Atualiza cache e força modo foco quando o WhatsApp Web está ativo."""
        nextHandler()
        self._in_whatsapp_web = self._check_whatsapp_web(obj)
        if self._in_whatsapp_web:
            if config.conf.get(CONFIG_SECTION, {}).get("autoFocusMode", True):
                ti = getattr(obj, "treeInterceptor", None)
                if ti and hasattr(ti, "passThrough") and not ti.passThrough:
                    ti.passThrough = True

    def event_liveRegionChange(self, obj, nextHandler):
        """Anuncia live regions do WhatsApp Web imediatamente, sem o delay polite."""
        if not self._in_whatsapp_web:
            return nextHandler()
        text = obj.name or obj.description or ""
        text = text.strip()
        if text:
            ui.message(text)
        # Não chama nextHandler: evita o anúncio duplicado com delay de 500ms
