# -*- coding: UTF-8 -*-
"""Classes de sobreposição (overlay) do WhatsApp para o NVDA.

Cada comportamento por objeto vive numa classe que o NVDA mistura ao objeto só
quando ele é uma linha do WhatsApp. Os atalhos de ``MessageRow`` valem enquanto
o foco está numa mensagem; fora dela a tecla segue para a página sem passar por
este add-on (``getScript`` devolve None).

Só objetos IAccessible entram aqui: misturar classes IAccessible e UIA gerou
objetos quebrados na 1.2.x.
"""

import api
import controlTypes
import oleacc
import ui
import winUser
from NVDAObjects import NVDAObject
from NVDAObjects.IAccessible import IAccessible, getNVDAObjectFromEvent
from NVDAObjects.IAccessible import chromium
from scriptHandler import script

import addonHandler

from . import messagetext, settings
from .context import (
	BROWSER_APPS,
	app_name_of,
	is_web_document,
	row_kind,
	web_title_hint,
	wa_context,
	APP_NAME,
)
from .tree import CELL_ROLES, ROW_ROLES, State, is_defunct, safe_role
from .webmode import WhatsAppWebDocument

addonHandler.initTranslation()

CATEGORY = _("WhatsApp Unificado")

# Janela de classe do WinUI que hospeda o WebView2 e janela do Chromium que desenha a página.
HOST_PANE_CLASS = "Microsoft.UI.Content.DesktopChildSiteBridge"
PAGE_WINDOW_CLASS = "Chrome_RenderWidgetHostHWND"


class ChatListRow(NVDAObject):
	"""Linha ou célula da lista de conversas. Não tem atalhos próprios."""

	wa_kind = "chat"

	def initOverlayClass(self):
		self.wa_kind = "chat"


class MessageRow(NVDAObject):
	"""Linha da lista de mensagens da conversa aberta."""

	wa_kind = "message"
	scriptCategory = CATEGORY

	def initOverlayClass(self):
		self.wa_kind = "message"

	# Tecla -> o que precisa existir na mensagem para a tecla ser nossa.
	_NEEDS = {
		"script_playMessage": messagetext.play_target,
		"script_audioToggle": lambda row: messagetext.find_player(row)[1],
		"script_audioSpeed": messagetext.speed_target,
	}

	def getScript(self, gesture):
		found = super().getScript(gesture)
		if found is None:
			return None
		if wa_context(self) is None:
			return None
		needs = self._NEEDS.get(getattr(found, "__name__", ""))
		if needs is not None and needs(self) is None:
			# Sem player nesta mensagem: a tecla é da página (Enter, Alt+P, Ctrl+S).
			return None
		return found

	@script(description=_("Tocar ou pausar mensagem de voz ou vídeo"), gesture="kb:enter")
	def script_playMessage(self, gesture):
		target = messagetext.play_target(self)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Pausar ou retomar o áudio da mensagem"), gesture="kb:alt+p")
	def script_audioToggle(self, gesture):
		buttons, slider = messagetext.find_player(self)
		if slider is None:
			gesture.send()
			return
		(buttons[-1] if buttons else slider).doAction()

	@script(description=_("Aumentar ou diminuir a velocidade do áudio"), gesture="kb:control+s")
	def script_audioSpeed(self, gesture):
		target = messagetext.speed_target(self)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Menu de contexto da mensagem"), gesture="kb:shift+enter")
	def script_contextMenu(self, gesture):
		button = messagetext.menu_button(self)
		if button is not None:
			button.doAction()
			return
		from keyboardHandler import KeyboardInputGesture

		KeyboardInputGesture.fromName("applications").send()

	@script(description=_("Reagir à mensagem"), gesture="kb:control+shift+enter")
	def script_reactMessage(self, gesture):
		button = messagetext.react_button(self)
		if button is None:
			ui.message(_("Botão de reação não encontrado"))
			return
		button.doAction()

	@script(description=_("Ler mensagem completa"), gesture="kb:control+r")
	def script_readFull(self, gesture):
		def speak(text):
			ui.message(text if text else _("Texto não encontrado"))

		messagetext.expand_then(self, speak)

	@script(description=_("Abrir mensagem em modo de navegação"), gesture="kb:alt+enter")
	def script_browseMessage(self, gesture):
		def show(text):
			if text:
				ui.browseableMessage(text, _("Mensagem"))
			else:
				ui.message(_("Texto não encontrado"))

		messagetext.expand_then(self, show)

	@script(description=_("Abrir mensagem em janela de texto"), gesture="kb:alt+c")
	def script_textWindow(self, gesture):
		def show(text):
			if not text:
				ui.message(_("Texto não encontrado"))
				return
			from .textwindow import TextWindow

			TextWindow(text, _("Mensagem"))

		messagetext.expand_then(self, show)

	@script(description=_("Copiar mensagem"), gesture="kb:control+c")
	def script_copyMessage(self, gesture):
		text = messagetext.message_text(self)
		if not text:
			gesture.send()
			return
		api.copyToClip(text)
		ui.message(_("Copiado"))


class SelectionPopup(IAccessible):
	"""Pop-up com papel menu que o WhatsApp abre ao selecionar texto no campo de digitação.

	Bug conhecido (nvda#19772), contornado pelo add-on "WhatsApp Desktop Access"
	de Eyalson (GPL-2), cuja ideia é usada aqui: com um campo editável em foco, o
	NVDA não deve levar o foco para esse menu.
	"""

	def _get_shouldAllowIAccessibleMenuStartEvent(self):
		if State.FOCUSED in self.states:
			return True
		focus = api.getFocusObject()
		if focus is not None and _is_editable(focus) and focus.windowHandle == self.windowHandle:
			return False
		return super()._get_shouldAllowIAccessibleMenuStartEvent()


def _is_editable(obj):
	try:
		states = obj.states
		if State.READONLY in states:
			return False
		return obj.role == controlTypes.Role.EDITABLETEXT or State.EDITABLE in states
	except Exception:
		return False


class _PageMemory:
	"""Último foco real dentro da página (para o painel-hospedeiro devolver o foco)."""

	hwnd = 0
	last = None


def note_page_focus(obj):
	"""Chamado a cada foco no WhatsApp: guarda a janela da página e o objeto focado."""
	try:
		if obj.windowClassName == PAGE_WINDOW_CLASS:
			_PageMemory.hwnd = obj.windowHandle
			_PageMemory.last = obj
	except Exception:
		pass


def real_page_focus():
	"""Elemento que de fato tem o foco do teclado na página, ou None."""
	hwnd = _PageMemory.hwnd
	if hwnd and winUser.isWindow(hwnd):
		try:
			document = getNVDAObjectFromEvent(hwnd, winUser.OBJID_CLIENT, 0)
			active = document.activeChild if document else None
			if active:
				return active
		except Exception:
			pass
	last = _PageMemory.last
	if last is not None and not is_defunct(last):
		return last
	return None


class HostPane(NVDAObject):
	"""Painel WinUI que hospeda o WebView2. Nunca tem foco útil.

	Quando o pop-up de seleção fecha, o foco cai aqui; devolvemos à página.
	Ideia do add-on de Eyalson (GPL-2).
	"""

	# O NVDA lê focusRedirect mais de uma vez por evento: calcula uma só.
	_cache_focusRedirect = True

	def _get_focusRedirect(self):
		target = real_page_focus()
		if target is None or target == self:
			return None
		return target


# ─── escolha das classes ─────────────────────────────────────────────────────

def choose_overlay_classes(obj, clsList, contexts):
	"""Insere as classes certas em ``clsList``. ``contexts`` ⊆ {"app", "web"}.

	Chamado para TODO objeto criado, então os testes baratos vêm primeiro:
	nome do aplicativo (local), depois escopo, depois papel.
	"""
	try:
		name = app_name_of(obj)
		if name == APP_NAME:
			ctx = "app"
		elif name in BROWSER_APPS:
			ctx = "web"
		else:
			return
		if ctx not in contexts or not settings.scope_allows(ctx):
			return

		if ctx == "app" and getattr(obj, "windowClassName", "") == HOST_PANE_CLASS:
			clsList.insert(0, HostPane)
			return

		if not isinstance(obj, IAccessible):
			return

		if ctx == "web" and any(issubclass(c, chromium.Document) for c in clsList):
			if is_web_document(obj):
				clsList.insert(0, WhatsAppWebDocument)
			return

		if ctx == "web" and not web_title_hint(obj):
			return

		try:
			is_popup = obj.IAccessibleRole == oleacc.ROLE_SYSTEM_MENUPOPUP
		except Exception:
			is_popup = False
		if is_popup:
			clsList.insert(0, SelectionPopup)
			return

		role = safe_role(obj)
		if role in ROW_ROLES or role in CELL_ROLES:
			kind = row_kind(obj)
			if kind == "chat":
				clsList.insert(0, ChatListRow)
			elif kind == "message":
				clsList.insert(0, MessageRow)
	except Exception:
		# Escolher classe nunca pode quebrar a criação do objeto.
		return
