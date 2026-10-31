# -*- coding: UTF-8 -*-
"""Classes de sobreposição (overlay) do WhatsApp para o NVDA.

Cada comportamento por objeto vive numa classe que o NVDA mistura ao objeto só
quando ele é uma linha do WhatsApp. Os atalhos de ``MessageRow`` valem enquanto
o foco está numa mensagem; fora do nosso caso ``getScript`` devolve exatamente
o que o NVDA devolveria sem o add-on.

Só objetos IAccessible entram aqui: misturar classes IAccessible e UIA gerou
objetos quebrados na 1.2.x.
"""

import re
import time

import api
import controlTypes
import inputCore
import oleacc
import speech
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
from .tree import CELL_ROLES, INNER_FOCUS_ROLES, ROW_ROLES, State, is_defunct, row_ancestor, safe_role
from .webmode import WhatsAppMenuDialog, WhatsAppWebDocument

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
		("kb:control+rightArrow", "nextWord"),
		("kb:control+leftArrow", "previousWord"),
	)
}

# Palavras da mensagem: qualquer sequência sem espaço (emoji e pontuação incluídos).
_WORD_RE = re.compile(r"\S+")


class _Words:
	"""Posição da leitura por palavra (2.0.7). Recomeça em outra mensagem ou se o texto muda."""

	message = None
	text = ""
	index = -1


def _reset_words():
	_Words.message = None
	_Words.text = ""
	_Words.index = -1


# Papéis que podem receber as classes de linha: a linha, a célula e o div focável.
_ROW_LIKE_ROLES = ROW_ROLES | CELL_ROLES | INNER_FOCUS_ROLES


class MessageRow(NVDAObject):
	"""Mensagem da conversa aberta: a linha (TABLEROW) ou o div focável dentro dela.

	O foco de verdade fica no div; os botões (reagir, menu, player) são irmãos
	dele dentro da linha. Por isso toda busca parte de ``wa_row``.
	"""

	wa_kind = "message"
	scriptCategory = CATEGORY
	_wa_ctx = "web"

	def initOverlayClass(self):
		self.wa_kind = "message"
		# Calculado uma vez, na criação: o que o getScript usa a cada tecla é só isto.
		self._wa_ctx = "web" if app_name_of(self) in BROWSER_APPS else "app"

	def _get_wa_row(self):
		"""A linha da mensagem (o próprio objeto, se for a linha). Lido só quando um comando roda."""
		if safe_role(self) in ROW_ROLES:
			return self
		return row_ancestor(self) or self

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
		target = messagetext.play_target(self.wa_row)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Pausar ou retomar o áudio da mensagem"))
	@diag.scripted
	def script_audioToggle(self, gesture):
		buttons, slider = messagetext.find_player(self.wa_row)
		if slider is None:
			gesture.send()
			return
		(buttons[-1] if buttons else slider).doAction()

	@script(description=_("Aumentar ou diminuir a velocidade do áudio"))
	@diag.scripted
	def script_audioSpeed(self, gesture):
		target = messagetext.speed_target(self.wa_row)
		if target is None:
			gesture.send()
			return
		target.doAction()

	@script(description=_("Menu de contexto da mensagem"))
	@diag.scripted
	def script_contextMenu(self, gesture):
		button = messagetext.menu_button(self.wa_row)
		if button is not None:
			button.doAction()
			return
		from keyboardHandler import KeyboardInputGesture

		KeyboardInputGesture.fromName("applications").send()

	@script(description=_("Reagir à mensagem"))
	@diag.scripted
	def script_reactMessage(self, gesture):
		button = messagetext.react_button(self.wa_row)
		if button is None:
			ui.message(_("Botão de reação não encontrado"))
			return
		button.doAction()

	@script(description=_("Ler próxima palavra da mensagem"))
	@diag.scripted
	def script_nextWord(self, gesture):
		self._speak_word(1, gesture)

	@script(description=_("Ler palavra anterior da mensagem"))
	@diag.scripted
	def script_previousWord(self, gesture):
		self._speak_word(-1, gesture)

	def _speak_word(self, direction, gesture):
		"""Ctrl+setas laterais: a mensagem palavra por palavra, sem sair dela.

		Relato do Leo (31/10/2026): na 1.4 dava para ler a mensagem palavra por
		palavra com o Ctrl e as setas; na 2.0 não, no aplicativo (que não tem
		modo de navegação) e no Web (que fica em modo foco). O WhatsApp só usa
		Ctrl+setas no tocador de áudio (velocidade), que é outro elemento; no div
		da mensagem a tecla não fazia nada. Em modo de navegação o buffer do NVDA
		pega a tecla antes (palavra do documento, nativo). Para nas pontas.
		"""
		text = messagetext.message_text(self.wa_row, focus=self)
		words = _WORD_RE.findall(text)
		if not words:
			gesture.send()
			return
		if _Words.message is not self or _Words.text != text:
			_Words.message = self
			_Words.text = text
			_Words.index = -1
		_Words.index = min(max(_Words.index + direction, 0), len(words) - 1)
		word = words[_Words.index]
		if len(word) == 1:
			speech.speakSpelling(word)
		else:
			speech.speakText(word)

	@script(description=_("Ler mensagem completa"))
	@diag.scripted
	def script_readFull(self, gesture):
		def speak(text):
			ui.message(text if text else _("Texto não encontrado"))

		messagetext.expand_then(self.wa_row, speak, focus=self)

	@script(description=_("Abrir mensagem em modo de navegação"))
	@diag.scripted
	def script_browseMessage(self, gesture):
		def show(text):
			if text:
				ui.browseableMessage(text, _("Mensagem"))
			else:
				ui.message(_("Texto não encontrado"))

		messagetext.expand_then(self.wa_row, show, focus=self)

	@script(description=_("Abrir mensagem em janela de texto"))
	@diag.scripted
	def script_textWindow(self, gesture):
		def show(text):
			if not text:
				ui.message(_("Texto não encontrado"))
				return
			from .textwindow import TextWindow

			TextWindow(text, _("Mensagem"))

		messagetext.expand_then(self.wa_row, show, focus=self)

	@script(description=_("Copiar mensagem"))
	@diag.scripted
	def script_copyMessage(self, gesture):
		if self._has_selection():
			# Há texto selecionado: o Ctrl+C é da página (copia só a seleção).
			gesture.send()
			return
		text = messagetext.message_text(self.wa_row, focus=self)
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
	_reset_words()


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
		started = time.monotonic()
		try:
			target = real_page_focus()
			if target is None or target is self:
				return None
			return target
		except Exception:
			return None
		finally:
			diag.slow("painel-hospedeiro", started)


# ─── escolha das classes ─────────────────────────────────────────────────────

def choose_overlay_classes(obj, clsList, contexts):
	"""Insere as classes certas em ``clsList``. ``contexts`` ⊆ {"app", "web"}.

	Chamado para TODO objeto criado, então os testes baratos vêm primeiro:
	nome do aplicativo (local), depois escopo, depois papel.
	"""
	started = time.monotonic()
	try:
		_choose(obj, clsList, contexts)
	except Exception:
		# Escolher classe nunca pode quebrar a criação do objeto.
		return
	finally:
		diag.slow("overlay", started)


def _note(cls, obj, extra=""):
	diag.act("overlay", "classe=%s%s %s" % (cls.__name__, extra, diag.describe(obj)), key="overlay:" + cls.__name__)


def _choose(obj, clsList, contexts):
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
		_note(HostPane, obj)
		return

	if not isinstance(obj, IAccessible):
		return

	if ctx == "web" and any(issubclass(c, chromium.Document) for c in clsList):
		if is_web_document(obj):
			clsList.insert(0, WhatsAppWebDocument)
			_note(WhatsAppWebDocument, obj)
		elif _is_dialog(obj) and web_overlay_allowed(obj):
			# Diálogo dentro do WhatsApp Web: o NVDA lhe daria um buffer próprio (webmode.py).
			clsList.insert(0, WhatsAppMenuDialog)
			_note(WhatsAppMenuDialog, obj)
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
		_note(SelectionPopup, obj)
		return

	if safe_role(obj) in _ROW_LIKE_ROLES:
		overlay = {"chat": ChatListRow, "message": MessageRow}.get(row_kind(obj))
		if overlay is not None:
			clsList.insert(0, overlay)
			_note(overlay, obj)


def _is_dialog(obj):
	try:
		return obj.IAccessibleRole == oleacc.ROLE_SYSTEM_DIALOG
	except Exception:
		return False


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
		if safe_role(obj) not in _ROW_LIKE_ROLES:
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
		_note(overlay, obj, " (na entrada)")
	except Exception:
		return
