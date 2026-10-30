# -*- coding: UTF-8 -*-
"""Classes de sobreposição (overlay) do WhatsApp para o NVDA.

Cada comportamento por objeto vive numa classe que o NVDA mistura ao objeto só
quando ele é uma linha do WhatsApp. Os atalhos de ``MessageRow`` valem enquanto
o foco está numa mensagem; fora do nosso caso ``getScript`` devolve exatamente
o que o NVDA devolveria sem o add-on.

Só objetos IAccessible entram aqui: misturar classes IAccessible e UIA gerou
objetos quebrados na 1.2.x.
"""

import api
import controlTypes
import inputCore
import oleacc
import textInfos
import ui
import winUser
from NVDAObjects import NVDAObject
from NVDAObjects.IAccessible import IAccessible, getNVDAObjectFromEvent
from NVDAObjects.IAccessible import chromium
from scriptHandler import script

import addonHandler

from . import diag, messagetext, settings
from .context import (
	BROWSER_APPS,
	app_name_of,
	is_web_document,
	row_kind,
	web_overlay_allowed,
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


# Teclas da linha de mensagem -> nome do script. NÃO são ligadas por
# ``@script(gesture=...)``: um gesto ligado na classe entra no mapa do objeto e
# esconde o que o NVDA ou outra classe tinha na mesma tecla, mesmo quando
# ``getScript`` devolve None. Aqui ``getScript`` consulta esta tabela e, fora do
# nosso caso, devolve exatamente o que o NVDA devolveria sem o add-on.
_MESSAGE_KEYS = {
	inputCore.normalizeGestureIdentifier(gesture): name
	for gesture, name in (
		("kb:enter", "playMessage"),
		("kb:alt+p", "audioToggle"),
		("kb:control+s", "audioSpeed"),
		("kb:shift+enter", "contextMenu"),
		("kb:control+shift+enter", "reactMessage"),
		("kb:control+r", "readFull"),
		("kb:alt+enter", "browseMessage"),
		("kb:alt+c", "textWindow"),
		("kb:control+c", "copyMessage"),
	)
}


class MessageRow(NVDAObject):
	"""Linha da lista de mensagens da conversa aberta."""

	wa_kind = "message"
	scriptCategory = CATEGORY
	_wa_ctx = "web"

	def initOverlayClass(self):
		self.wa_kind = "message"
		# Calculado uma vez, na criação: o que o getScript usa a cada tecla é só isto.
		self._wa_ctx = "web" if app_name_of(self) in BROWSER_APPS else "app"

	def getScript(self, gesture):
		"""Decisão BARATA: sem caminhar pela árvore (roda no gancho de teclado).

		Quem decide se há player, texto ou botão é o próprio script, que, se não
		for o caso, repassa a tecla com ``gesture.send()`` (local à linha).
		"""
		# Só vale com o foco confirmado no WhatsApp (contexto do último evento de
		# foco): uma sobreposição que ficou num objeto de outra página não age.
		if wa_context(self) == self._wa_ctx:
			try:
				identifiers = gesture.normalizedIdentifiers
			except Exception:
				identifiers = ()
			for identifier in identifiers:
				name = _MESSAGE_KEYS.get(identifier)
				if name is not None:
					return getattr(self, "script_" + name)
		return super().getScript(gesture)

	@script(description=_("Tocar ou pausar mensagem de voz ou vídeo"))
	@diag.scripted
	def script_playMessage(self, gesture):
		target = messagetext.play_target(self)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Pausar ou retomar o áudio da mensagem"))
	@diag.scripted
	def script_audioToggle(self, gesture):
		buttons, slider = messagetext.find_player(self)
		if slider is None:
			gesture.send()
			return
		(buttons[-1] if buttons else slider).doAction()

	@script(description=_("Aumentar ou diminuir a velocidade do áudio"))
	@diag.scripted
	def script_audioSpeed(self, gesture):
		target = messagetext.speed_target(self)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Menu de contexto da mensagem"))
	@diag.scripted
	def script_contextMenu(self, gesture):
		button = messagetext.menu_button(self)
		if button is not None:
			button.doAction()
			return
		from keyboardHandler import KeyboardInputGesture

		KeyboardInputGesture.fromName("applications").send()

	@script(description=_("Reagir à mensagem"))
	@diag.scripted
	def script_reactMessage(self, gesture):
		button = messagetext.react_button(self)
		if button is None:
			ui.message(_("Botão de reação não encontrado"))
			return
		button.doAction()

	@script(description=_("Ler mensagem completa"))
	@diag.scripted
	def script_readFull(self, gesture):
		def speak(text):
			ui.message(text if text else _("Texto não encontrado"))

		messagetext.expand_then(self, speak)

	@script(description=_("Abrir mensagem em modo de navegação"))
	@diag.scripted
	def script_browseMessage(self, gesture):
		def show(text):
			if text:
				ui.browseableMessage(text, _("Mensagem"))
			else:
				ui.message(_("Texto não encontrado"))

		messagetext.expand_then(self, show)

	@script(description=_("Abrir mensagem em janela de texto"))
	@diag.scripted
	def script_textWindow(self, gesture):
		def show(text):
			if not text:
				ui.message(_("Texto não encontrado"))
				return
			from .textwindow import TextWindow

			TextWindow(text, _("Mensagem"))

		messagetext.expand_then(self, show)

	@script(description=_("Copiar mensagem"))
	@diag.scripted
	def script_copyMessage(self, gesture):
		if self._has_selection():
			# Há texto selecionado: o Ctrl+C é da página (copia só a seleção).
			gesture.send()
			return
		text = messagetext.message_text(self)
		if not text:
			gesture.send()
			return
		api.copyToClip(text)
		ui.message(_("Copiado"))


	def _has_selection(self):
		"""Há texto selecionado na linha (ou no documento)? Qualquer dúvida = não."""
		holders = [self]
		try:
			holder = self.treeInterceptor
		except Exception:
			holder = None
		if holder is not None:
			holders.append(holder)
		for item in holders:
			try:
				info = item.makeTextInfo(textInfos.POSITION_SELECTION)
				if not info.isCollapsed:
					return True
			except Exception:
				continue
		return False


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


def reset_page_memory():
	"""Solta as referências (chamado ao encerrar o plugin e na recarga)."""
	_PageMemory.hwnd = 0
	_PageMemory.last = None


def note_page_focus(obj):
	"""Chamado a cada foco no WhatsApp: guarda a janela da página e o objeto focado."""
	try:
		if obj.windowClassName == PAGE_WINDOW_CLASS:
			_PageMemory.hwnd = obj.windowHandle
			_PageMemory.last = obj
	except Exception:
		pass


def _usable(obj):
	"""Objeto ainda vivo? Objeto morto (linha desmontada, erro de COM) não serve."""
	if obj is None:
		return False
	return not is_defunct(obj)


def real_page_focus():
	"""Elemento que de fato tem o foco do teclado na página, ou None."""
	hwnd = _PageMemory.hwnd
	if hwnd and winUser.isWindow(hwnd):
		try:
			document = getNVDAObjectFromEvent(hwnd, winUser.OBJID_CLIENT, 0)
			active = document.activeChild if document else None
			if _usable(active):
				return active
		except Exception:
			pass
	last = _PageMemory.last
	if _usable(last):
		return last
	_PageMemory.last = None
	return None


class HostPane(NVDAObject):
	"""Painel WinUI que hospeda o WebView2. Nunca tem foco útil.

	Quando o pop-up de seleção fecha, o foco cai aqui; devolvemos à página.
	Ideia do add-on de Eyalson (GPL-2).
	"""

	# O NVDA lê focusRedirect mais de uma vez por evento: calcula uma só.
	_cache_focusRedirect = True

	def _get_focusRedirect(self):
		try:
			target = real_page_focus()
			if target is None or target is self:
				return None
			return target
		except Exception:
			return None


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
			diag.act("overlay", "classe=HostPane " + diag.describe(obj))
			return

		if not isinstance(obj, IAccessible):
			return

		if ctx == "web" and any(issubclass(c, chromium.Document) for c in clsList):
			if is_web_document(obj):
				clsList.insert(0, WhatsAppWebDocument)
				diag.act("overlay", "classe=WhatsAppWebDocument " + diag.describe(obj))
			return

		# Objeto de navegador: só se o foco ATUAL já foi confirmado como
		# web.whatsapp.com (pelo endereço, no evento de foco) e o objeto é da mesma
		# janela. Comparação barata: nenhuma chamada ao navegador, em nenhum site.
		if ctx == "web" and not web_overlay_allowed(obj):
			return

		try:
			is_popup = obj.IAccessibleRole == oleacc.ROLE_SYSTEM_MENUPOPUP
		except Exception:
			is_popup = False
		if is_popup:
			clsList.insert(0, SelectionPopup)
			diag.act("overlay", "classe=SelectionPopup " + diag.describe(obj))
			return

		role = safe_role(obj)
		if role in ROW_ROLES or role in CELL_ROLES:
			kind = row_kind(obj)
			if kind == "chat":
				clsList.insert(0, ChatListRow)
			elif kind == "message":
				clsList.insert(0, MessageRow)
			if kind in ("chat", "message"):
				diag.act("overlay", "classe=%s %s" % (clsList[0].__name__, diag.describe(obj)))
	except Exception:
		# Escolher classe nunca pode quebrar a criação do objeto.
		return


_upgraded = {}


def upgrade_focus_object(obj):
	"""O objeto de foco da ENTRADA no WhatsApp nasceu antes de o contexto ser confirmado.

	O NVDA cria o objeto de foco antes do evento de foco; na primeira vez que o
	foco chega ao WhatsApp Web o contexto ainda não existia e a linha ficou sem
	sobreposição. Aqui (já confirmado, uma vez por entrada) ela recebe a classe,
	do mesmo jeito que o NVDA muda a classe de um objeto recém-criado. Qualquer
	dúvida: não faz nada.
	"""
	try:
		if getattr(obj, "wa_kind", None) or not isinstance(obj, IAccessible):
			return
		role = safe_role(obj)
		if role not in ROW_ROLES and role not in CELL_ROLES:
			return
		kind = row_kind(obj)
		overlay = {"chat": ChatListRow, "message": MessageRow}.get(kind)
		if overlay is None:
			return
		base = type(obj)
		if issubclass(base, overlay):
			return
		new = _upgraded.get((base, overlay))
		if new is None:
			new = type("Dynamic_%s%s" % (overlay.__name__, base.__name__), (overlay, base), {"__module__": __name__})
			_upgraded[(base, overlay)] = new
		obj.__class__ = new
		init = overlay.__dict__.get("initOverlayClass")
		if init is not None:
			init(obj)
		diag.act("overlay", "classe=%s (na entrada) %s" % (overlay.__name__, diag.describe(obj)))
	except Exception:
		return
