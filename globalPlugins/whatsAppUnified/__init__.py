# -*- coding: UTF-8 -*-
"""WhatsApp Unificado 2.0: plugin global (WhatsApp Web e comandos do conjunto).

O módulo do aplicativo (appModules/whatsapp_root.py) é fino e usa este pacote.
Aqui ficam os comandos globais (valem no app e no Web), os filtros de fala, a
recuperação de foco e a escolha de classes de sobreposição para o Web.

REGRA DE OURO: nenhum script daqui engole uma tecla. ``getScript`` devolve None
fora do WhatsApp (ou fora do escopo escolhido), e a tecla segue intacta para o
NVDA e para o programa. A 1.4.x engolia NVDA+Espaço e NVDA+Shift+I no sistema
inteiro porque o fallback era ``gesture.send()``.
"""

import addonHandler
import api
import globalPluginHandler
import ui
from logHandler import log
from scriptHandler import script
from speech.extensions import filter_speechSequence

from . import context, diag, filters, messagetext, overlays, recovery, settings, tree, webmode
from .context import document_url, find_document, forget_kinds, forget_web, raw_context, wa_context

addonHandler.initTranslation()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	# Translators: categoria dos comandos em "Gestos de entrada".
	scriptCategory = _("WhatsApp Unificado")

	def __init__(self):
		super().__init__()
		settings.register_config()
		settings.add_panel()
		filter_speechSequence.register(filters.on_speech_sequence)
		recovery.reset()
		diag.reset()
		recovery.register_keys()

	def terminate(self):
		filter_speechSequence.unregister(filters.on_speech_sequence)
		recovery.unregister_keys()
		recovery.reset()
		# Solta referências a objetos do WhatsApp e vereditos guardados (a recarga
		# do NVDA+Ctrl+F3 cria um pacote novo; nada pode ficar apontando para o velho).
		overlays.reset_page_memory()
		webmode.forget_entry()
		forget_web()
		forget_kinds()
		settings.remove_panel()
		super().terminate()

	# ─── nunca engolir tecla ─────────────────────────────────────────────────

	def getScript(self, gesture):
		"""Fora do WhatsApp (ou do escopo) devolve None.

		Conferido no NVDA 2026.2 (scriptHandler._findScript): o NVDA percorre o
		objeto em foco, o buffer, o módulo do aplicativo e CADA plugin global em
		ordem, e usa o primeiro script achado. Um plugin que devolve None é como
		se não existisse: a tecla segue para os outros plugins e para o mapa
		global do NVDA. O mapa deste plugin só tem os nossos comandos, então não
		há nada nativo para "devolver" aqui.
		"""
		if context.active() is None:  # foco fora do WhatsApp: nada a fazer, sem COM
			return None
		found = super().getScript(gesture)
		if found is None:
			return None
		if not self._in_whatsapp():
			return None
		return found

	@staticmethod
	def _in_whatsapp():
		try:
			return wa_context() is not None
		except Exception:
			return False

	@staticmethod
	def _root():
		"""Raiz do documento do foco; só o aplicativo aceita a janela inteira como reserva."""
		try:
			focus = api.getFocusObject()
			return tree.document_root(focus, allow_foreground=raw_context(focus) == "app")
		except Exception:
			return None

	# ─── objetos e eventos ───────────────────────────────────────────────────

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		# O lado "app" é escolhido pelo módulo do aplicativo; aqui só o Web.
		# Para programa que não é navegador, ``choose_overlay_classes`` sai na
		# primeira linha (só lê o nome do programa).
		overlays.choose_overlay_classes(obj, clsList, {"web"})

	def event_gainFocus(self, obj, nextHandler):
		# Primeira coisa: decidir, UMA vez, onde o foco está. Fora do WhatsApp e
		# fora de um navegador isto lê só o nome do programa (sem COM) e o
		# evento segue intacto.
		was_web = context.active() == "web"
		kind = context.update_focus(obj)
		if kind is None:
			if was_web:
				webmode.restore_last_mode()
				diag.act("contexto", "saiu do WhatsApp Web", key="contexto:saiu")
			nextHandler()
			return
		if kind == "web" and not was_web:
			diag.act("contexto", "WhatsApp Web confirmado " + diag.describe(obj), key="contexto:web")
			overlays.upgrade_focus_object(obj)
		elif kind == "app":
			if was_web:
				webmode.restore_last_mode()
			diag.act("contexto", "aplicativo do WhatsApp " + diag.describe(obj), key="contexto:app")
		called = []

		def deliver():
			called.append(True)
			nextHandler()

		handled = False
		try:
			if wa_context() is not None:
				overlays.note_page_focus(obj)
				handled = recovery.handle_gain_focus(obj, deliver)
		except Exception:
			log.debugWarning("WhatsApp Unificado: falha ao tratar o foco", exc_info=True)
			handled = bool(called)
		if not handled:
			nextHandler()

	# ─── comandos globais ────────────────────────────────────────────────────

	@script(description=_("Ir para lista de conversas"), gesture="kb:alt+1")
	@diag.scripted
	def script_goToChatList(self, gesture):
		container = tree.find_chat_list(self._root(), tree.new_deadline())
		if container is None:
			ui.message(_("Lista de conversas não encontrada"))
			return
		target = tree.selected_or_first(tree.rows_of(container)) or container
		target.setFocus()

	@script(description=_("Ir para lista de mensagens"), gesture="kb:alt+2")
	@diag.scripted
	def script_goToMessageList(self, gesture):
		container = tree.find_message_list(self._root(), tree.new_deadline())
		if container is None:
			ui.message(_("Lista de mensagens não encontrada"))
			return
		for child in tree.iter_children_reversed(container, limit=60):
			if tree.safe_role(child) in tree.ROW_ROLES:
				child.setFocus()
				return
		container.setFocus()

	@script(description=_("Ir para campo de digitação"), gesture="kb:alt+d")
	@diag.scripted
	def script_focusComposer(self, gesture):
		composer = tree.find_composer(self._root(), deadline=tree.new_deadline())
		if composer is None:
			ui.message(_("Campo de digitação não encontrado"))
			return
		composer.setFocus()

	@script(description=_("Abrir menu de chamada"), gesture="kb:shift+alt+c")
	@diag.scripted
	def script_openCallMenu(self, gesture):
		button = messagetext.call_button(self._root(), tree.new_deadline())
		if button is None:
			ui.message(_("Botão de chamada não encontrado"))
			return
		button.doAction()

	@script(description=_("Alternar filtro de números de telefone"), gesture="kb:control+shift+e")
	@diag.scripted
	def script_togglePhoneFilter(self, gesture):
		value = not settings.get("filterMessageList")
		settings.put("filterMessageList", value)
		state = _("ativado") if value else _("desativado")
		ui.message(_("Filtro de telefone {state}").format(state=state))

	@script(description=_("Alternar filtro de dicas de uso"), gesture="kb:NVDA+shift+h")
	@diag.scripted
	def script_toggleHintsFilter(self, gesture):
		value = not settings.get("filterUsageHints")
		settings.put("filterUsageHints", value)
		state = _("ativado") if value else _("desativado")
		ui.message(_("Filtro de dicas {state}").format(state=state))

	# Sem gesto padrão: o usuário atribui em Gestos de entrada, se quiser.
	@script(description=_("Inspecionar elemento do WhatsApp (papel, nome, estados, endereço)"))
	@diag.scripted
	def script_inspector(self, gesture):
		obj = api.getFocusObject()
		try:
			location = obj.location
			where = (
				"E:{0} T:{1} L:{2} A:{3}".format(location.left, location.top, location.width, location.height)
				if location
				else "sem posição"
			)
		except Exception:
			where = "sem posição"
		try:
			attributes = getattr(obj, "IA2Attributes", {}) or {}
			css = attributes.get("class", "")[:60]
		except Exception:
			css = ""
		role = getattr(obj.role, "displayString", str(obj.role))
		states = ", ".join(getattr(s, "displayString", str(s)) for s in getattr(obj, "states", set()))
		doc = find_document(obj)
		url = document_url(doc) if doc is not None else ""
		ui.message(
			"Contexto:{ctx} | Papel:{role} | {where} | Nome:'{name}' | Classe:{css} | "
			"Estados:{states} | Endereço:{url}".format(
				ctx=raw_context(obj) or "nenhum",
				role=role,
				where=where,
				name=(obj.name or "")[:50],
				css=css,
				states=states,
				url=url or "",
			),
		)
