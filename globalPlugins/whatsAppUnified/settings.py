# -*- coding: UTF-8 -*-
"""WhatsApp Unificado: configuração (lida ao vivo) e painel de opções do NVDA.

As opções são lidas da configuração do NVDA a cada uso, então mudar algo no
painel vale na hora, sem reiniciar o NVDA. Chaves antigas (por exemplo
``disableFocusLock``) são toleradas: o NVDA as mantém no arquivo e este módulo
só as consulta quando faz sentido.
"""

import addonHandler
import config
import gui
import wx
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel

addonHandler.initTranslation()

CONFIG_SECTION = "whatsAppUnified"

SPEC = {
	"scope": "string(default='both')",  # 'desktop', 'web' ou 'both'
	"filterMessageList": "boolean(default=True)",  # telefone nas mensagens
	"filterChatList": "boolean(default=False)",  # telefone na lista de conversas
	"filterUsageHints": "boolean(default=True)",
	"filterTalvez": "boolean(default=True)",
	"autoFocusMode": "boolean(default=True)",  # modo foco automático no WhatsApp Web
	"focusRecovery": "boolean(default=True)",  # recuperar o foco perdido
}

DEFAULTS = {
	"scope": "both",
	"filterMessageList": True,
	"filterChatList": False,
	"filterUsageHints": True,
	"filterTalvez": True,
	"autoFocusMode": True,
	"focusRecovery": True,
}

SCOPE_CHOICES = [
	("desktop", _("Apenas aplicativo (Desktop)")),
	("web", _("Apenas WhatsApp Web (navegador)")),
	("both", _("Ambos")),
]


def register_config():
	"""Registra a seção de configuração. Chamado uma vez pelo plugin global."""
	config.conf.spec[CONFIG_SECTION] = SPEC
	if CONFIG_SECTION not in config.conf:
		config.conf[CONFIG_SECTION] = {}


def get(key):
	"""Valor atual de uma opção (ao vivo). Nunca levanta exceção."""
	default = DEFAULTS.get(key)
	try:
		section = config.conf[CONFIG_SECTION]
		value = section[key] if key in section else default
	except Exception:
		return default
	if key == "autoFocusMode":
		# Migração: 'disableFocusLock' (1.x) desligava o modo foco automático.
		try:
			if section.get("disableFocusLock", False):
				return False
		except Exception:
			pass
	return value


def put(key, value):
	"""Grava uma opção e salva a configuração."""
	config.conf[CONFIG_SECTION][key] = value
	config.conf.save()


def scope_allows(kind):
	"""Diz se o escopo escolhido cobre o contexto ``kind`` ('app' ou 'web')."""
	scope = get("scope")
	if scope == "both" or scope not in ("desktop", "web"):
		return True
	return (scope == "desktop" and kind == "app") or (scope == "web" and kind == "web")


class WhatsAppUnifiedSettings(SettingsPanel):
	# Translators: título do painel nas configurações do NVDA.
	title = _("WhatsApp Unificado")

	def makeSettings(self, settingsSizer):
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		labels = [label for _key, label in SCOPE_CHOICES]
		self.scope = helper.addLabeledControl(_("Aplicar para:"), wx.Choice, choices=labels)
		keys = [key for key, _label in SCOPE_CHOICES]
		current = get("scope")
		self.scope.SetSelection(keys.index(current) if current in keys else keys.index("both"))

		self.filterMessageList = helper.addItem(
			wx.CheckBox(self, label=_("Filtrar números de telefone nas mensagens")),
		)
		self.filterMessageList.SetValue(bool(get("filterMessageList")))

		self.filterChatList = helper.addItem(
			wx.CheckBox(self, label=_("Filtrar números de telefone na lista de conversas")),
		)
		self.filterChatList.SetValue(bool(get("filterChatList")))

		self.filterUsageHints = helper.addItem(
			wx.CheckBox(self, label=_("Silenciar dicas de uso ('Para mais opções...')")),
		)
		self.filterUsageHints.SetValue(bool(get("filterUsageHints")))

		self.filterTalvez = helper.addItem(
			wx.CheckBox(self, label=_("Remover 'Talvez' antes de nomes de contato")),
		)
		self.filterTalvez.SetValue(bool(get("filterTalvez")))

		self.autoFocusMode = helper.addItem(
			wx.CheckBox(
				self,
				label=_("Manter o modo foco automaticamente no WhatsApp Web, sem som de troca de modo"),
			),
		)
		self.autoFocusMode.SetValue(bool(get("autoFocusMode")))

		self.focusRecovery = helper.addItem(
			wx.CheckBox(self, label=_("Recuperar o foco quando o WhatsApp o perde")),
		)
		self.focusRecovery.SetValue(bool(get("focusRecovery")))

	def onSave(self):
		section = config.conf[CONFIG_SECTION]
		keys = [key for key, _label in SCOPE_CHOICES]
		section["scope"] = keys[self.scope.GetSelection()]
		section["filterMessageList"] = self.filterMessageList.IsChecked()
		section["filterChatList"] = self.filterChatList.IsChecked()
		section["filterUsageHints"] = self.filterUsageHints.IsChecked()
		section["filterTalvez"] = self.filterTalvez.IsChecked()
		section["autoFocusMode"] = self.autoFocusMode.IsChecked()
		section["focusRecovery"] = self.focusRecovery.IsChecked()
		# O interruptor antigo deixa de valer quando o usuário salva o painel novo.
		if "disableFocusLock" in section:
			section["disableFocusLock"] = False
		config.conf.save()


def add_panel():
	if WhatsAppUnifiedSettings not in NVDASettingsDialog.categoryClasses:
		NVDASettingsDialog.categoryClasses.append(WhatsAppUnifiedSettings)


def remove_panel():
	if WhatsAppUnifiedSettings in NVDASettingsDialog.categoryClasses:
		NVDASettingsDialog.categoryClasses.remove(WhatsAppUnifiedSettings)
