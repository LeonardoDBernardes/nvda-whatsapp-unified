# -*- coding: UTF-8 -*-
"""Modo foco estável no WhatsApp Web, sem o som de troca de modo.

PROBLEMA (relato do Leo, 22/10/2026): "fica dando o barulho do NVDA como se eu
estivesse usando insert+espaço" a cada troca de foco no WhatsApp Web.

CAUSA, conferida no código do NVDA 2026.2 (browseMode.py):
- a cada evento de foco, ``BrowseModeDocumentTreeInterceptor.event_gainFocus``
  e ``_set_selection`` perguntam ``shouldPassThrough(obj, reason)``. A resposta
  muda de objeto para objeto: campo de digitação e células (TABLECELL) = modo
  foco; linhas (TABLEROW) e botões = modo de navegação;
- ``reportPassThrough`` compara o modo novo com ``reportPassThrough.last``, uma
  variável GLOBAL, e toca focusMode.wav / browseMode.wav toda vez que diferem.
  Ao passar de uma linha para o campo de digitação (ou para uma célula) e voltar,
  o som toca a cada troca. Entrar no documento vindo de outra aba também toca
  (o ``.last`` é de outro documento).

SOLUÇÃO: uma subclasse do buffer do Chromium, ``WhatsAppChromeVBuf``,
escolhida por sobreposição do documento
(``WhatsAppWebDocument._get_treeInterceptorClass``). Ela
1. NASCE em modo foco: ``_passThrough = True`` (privado de propósito: o setter
   público chamaria ``_focusLastFocusableObject`` e puxaria o foco do usuário)
   e com a trava própria ``_wa_lock`` ligada. NÃO usa ``disableAutoPassThrough``
   (a 2.0.0 e a 2.0.1 usavam, e isso mudava o Esc; ver abaixo);
2. sincroniza ``reportPassThrough.last`` com o modo dela ao nascer, ao ganhar
   o foco e a cada evento de foco. Assim entrar no documento é SILENCIOSO;
3. responde SEMPRE a mesma coisa em ``shouldPassThrough(obj, FOCUS|CARET)``
   enquanto a trava está ligada (True). Sem resposta variável não há troca
   de modo; sem troca de modo ``reportPassThrough`` nunca toca.

ESC (2.0.9, igual ao aplicativo): com a trava ligada o Esc vai ao WhatsApp,
sem trocar de modo e sem som. Relato do Leo (31/10/2026): no aplicativo, Esc
numa mensagem volta para a lista de conversas; no Web o Esc era o do NVDA
(modo de navegação, com o som) e o Esc seguinte, já em modo de navegação, ia
para a página e deixava a conversa e a lista "bagunçadas". O Esc nativo tinha
ficado na 2.0.2 por causa do "Espaço e depois Esc" para abrir o menu; desde a
2.0.4 esse Esc de costume é tratado dentro do menu (menu.py), e desde a 2.0.7
o Ctrl+setas lê a mensagem por palavra em modo foco. O modo de navegação
continua no NVDA+Espaço. Dentro de um menu do WhatsApp o plugin global pega o
Esc antes do buffer (2.0.3, ver menu.py).

ROLAGEM (2.0.10): com a trava ligada a rolagem da página não move o cursor nem o
foco (``event_scrollingStart``); antes ela tirava o foco do menu da mensagem.

O QUE CONTINUA NATIVO:
- NVDA+Espaço alterna normalmente e toca o som, porque o ``.last`` está
  sincronizado com o modo anterior. Em modo de navegação escolhido assim a
  trava só volta em campo de texto ou com NVDA+Espaço de novo;
- outros sites: a sobreposição só vale se o endereço do documento é
  ``web.whatsapp.com``; qualquer outro documento usa o ChromeVBuf original.
  Se o mesmo buffer navegar para outro endereço, o veredito é refeito e o modo
  foco fixo é solto.

LIMITES (documentados no README): vale para o Chromium com IAccessible2, que é o
padrão do NVDA (``allowInChromium = 0``). Se o usuário ligou UI Automation para
navegadores baseados em Chromium, o buffer não é um ChromeVBuf e nada aqui roda.
Sair do WhatsApp para uma página em modo de navegação pode tocar UM som, o
mesmo que o NVDA toca ao mudar de modo entre documentos.
"""

import api
import browseMode
import controlTypes
from controlTypes import OutputReason
from NVDAObjects.IAccessible import chromium
from NVDAObjects.IAccessible.chromium import ChromeVBuf

from . import diag, menu, settings
from .context import is_web_document, ti_verdict


class _Entry:
	"""O ``reportPassThrough.last`` de ANTES de o add-on fixar o modo foco (para devolver ao sair)."""

	last = None


def restore_last_mode():
	"""O foco saiu do WhatsApp Web: devolve ao NVDA o "último modo anunciado" de antes.

	Sem isto, trocar para outra aba em modo de navegação tocaria um som que o
	NVDA nativo não tocaria (o ``.last`` ficaria preso em "modo foco" do
	WhatsApp). É a única escrita em ``reportPassThrough.last`` feita com o foco
	fora do WhatsApp, e só acontece se o add-on tinha fixado o modo antes.
	"""
	if _Entry.last is None:
		return
	value = _Entry.last
	_Entry.last = None
	browseMode.reportPassThrough.last = value
	diag.act("modo-foco-devolvido", "ultimo_modo=%s" % ("foco" if value else "navegacao"))


def forget_entry():
	_Entry.last = None


def editable_and_available(obj):
	"""Campo de texto editável e disponível (a regra nativa de entrada de texto)."""
	try:
		states = obj.states
	except Exception:
		return False
	return controlTypes.State.EDITABLE in states and controlTypes.State.UNAVAILABLE not in states


class WhatsAppChromeVBuf(ChromeVBuf):
	"""Buffer do Chromium para documentos do WhatsApp Web, em modo foco fixo.

	O veredito (este documento é o WhatsApp Web?) vem do ENDEREÇO e é refeito
	sempre que o endereço do documento muda: se o mesmo buffer navegar para
	outro site, o modo foco é solto e o buffer volta a se comportar como o
	original. A opção "manter o modo foco automaticamente" também vale na hora,
	sem recarregar a página (na próxima decisão de foco).
	"""

	_wa_verdict = False  # só vira True com o endereço confirmado (nunca por suposição)
	_wa_pinned = False  # o add-on cuida do modo deste buffer (WhatsApp Web + opção ligada)
	_wa_lock = False  # trava: modo foco sem troca, para qualquer objeto

	def __init__(self, rootNVDAObject):
		super().__init__(rootNVDAObject)
		# A classe pode ter sido escolhida quando o documento ainda apontava para o
		# WhatsApp e o mesmo objeto depois navegou: confirma o endereço de novo.
		verdict = ti_verdict(self)
		if verdict is None:
			try:
				verdict = is_web_document(rootNVDAObject)
			except Exception:
				verdict = False
		self._wa_verdict = bool(verdict)
		self._wa_update(write_last=False)

	# ─── veredito e fixação do modo foco ────────────────────────────────────

	def _wa_enabled(self):
		return settings.scope_allows("web") and bool(settings.get("autoFocusMode"))

	def _wa_is_active_buffer(self):
		"""Este buffer é o do foco atual? Só ele pode mexer em ``reportPassThrough.last``."""
		try:
			return api.getFocusObject().treeInterceptor is self
		except Exception:
			return False

	def _wa_update(self, write_last=True):
		"""Fixa ou solta o modo foco conforme o endereço atual e a opção."""
		verdict = ti_verdict(self)  # lê o endereço atual (o NVDA guarda por ciclo)
		if verdict is not None:
			self._wa_verdict = verdict
		want = self._wa_verdict and self._wa_enabled()
		mine = write_last and self._wa_is_active_buffer()
		if want and not self._wa_pinned:
			self._wa_pinned = True
			self._wa_lock = True
			self._passThrough = True
			if mine:
				if _Entry.last is None:
					_Entry.last = bool(browseMode.reportPassThrough.last)
				browseMode.reportPassThrough.last = True
			diag.act("modo-foco-fixado", "buffer=WhatsApp")
		elif self._wa_pinned and not want:
			self._wa_pinned = False
			self._wa_lock = False
			# Volta à regra nativa para o objeto em foco (sem som: o "último modo
			# anunciado" passa a ser o modo novo).
			self._passThrough = self._native_pass_through_for_focus()
			if mine:
				browseMode.reportPassThrough.last = self._passThrough
				_Entry.last = None
			diag.act("modo-foco-solto", "motivo=%s" % ("endereco" if not self._wa_verdict else "opcao"))

	def _native_pass_through_for_focus(self):
		try:
			focus = api.getFocusObject()
			if focus is not None:
				return bool(super().shouldPassThrough(focus, OutputReason.FOCUS))
		except Exception:
			pass
		return False

	def _wa_sync_last(self):
		"""Faz o "último modo anunciado" do NVDA coincidir com o deste documento."""
		if self._wa_pinned and self._wa_is_active_buffer():
			if _Entry.last is None:
				_Entry.last = bool(browseMode.reportPassThrough.last)
			browseMode.reportPassThrough.last = self.passThrough

	# ─── decisão de modo ─────────────────────────────────────────────────────

	def _wa_follow_user(self):
		"""Acompanha o que o usuário fez com Esc e NVDA+Espaço."""
		if self._wa_lock and not self.passThrough:
			# Saiu do modo foco (NVDA+Espaço): o modo de navegação é dele.
			self._wa_lock = False
		elif not self._wa_lock and self.passThrough:
			# Voltou ao modo foco (NVDA+Espaço, campo de texto): trava de novo. O
			# NVDA+Espaço liga ``disableAutoPassThrough``, que mandaria o próximo
			# Esc à página; a trava do add-on faz o papel dele.
			self._wa_lock = True
			self._disableAutoPassThrough = False

	def _wa_relock(self, obj):
		"""Em modo de navegação, este foco deve voltar ao modo foco travado?

		Menu do WhatsApp também volta (2.0.3): em modo de navegação as setas
		sairiam do menu para as mensagens. O plugin global trata o foco antes do
		buffer, então ``menu.active()`` já é o menu deste foco.
		"""
		if editable_and_available(obj):
			return True
		return menu.active() is not None

	def shouldPassThrough(self, obj, reason=None):
		self._wa_update()
		if reason in (OutputReason.FOCUS, OutputReason.CARET) and self._wa_pinned:
			self._wa_follow_user()
			if self._wa_lock:
				# Trava ligada: SEMPRE a mesma resposta, para qualquer objeto.
				return True
			if reason == OutputReason.CARET:
				return super().shouldPassThrough(obj, reason)  # cursor do modo de navegação: nativo
			if self._wa_relock(obj):
				self._wa_lock = True
				return True
			return False
		return super().shouldPassThrough(obj, reason)

	def _set_passThrough(self, state):
		"""Toda troca de modo feita pelo NVDA (Esc, NVDA+Espaço, foco) passa aqui; só registra.

		As escritas do próprio add-on em ``_passThrough`` são silenciosas de
		propósito e não passam por aqui.
		"""
		if self._wa_pinned and bool(state) != bool(self._passThrough):
			try:
				where = diag.describe(api.getFocusObject())
			except Exception:
				where = "?"
			diag.act(
				"modo-trocou",
				"para=%s trava=%s menu=%s %s" % (
					"foco" if state else "navegacao",
					self._wa_lock,
					menu.active() is not None,
					where,
				),
				key="modo-trocou:%s" % bool(state),
			)
		super()._set_passThrough(state)

	def script_disablePassThrough(self, gesture):
		"""Esc em modo foco: vai ao WhatsApp, como no aplicativo (2.0.9, ver o topo).

		Em modo de navegação (escolhido com NVDA+Espaço) e com a opção de manter
		o modo foco desligada, o Esc é o nativo do NVDA.
		"""
		if self._wa_pinned and self.passThrough:
			self._wa_lock = True
			self._disableAutoPassThrough = False
			try:
				where = diag.describe(api.getFocusObject())
			except Exception:
				where = "?"
			diag.act("esc-para-whatsapp", where)
			gesture.send()
			return
		super().script_disablePassThrough(gesture)

	script_disablePassThrough.ignoreTreeInterceptorPassThrough = True

	def event_scrollingStart(self, obj, nextHandler):
		"""Rolagem da página em modo foco travado: o cursor e o foco ficam onde estão (2.0.10).

		Relato do Leo (31/10/2026): descendo pelas opções do menu da mensagem, no
		Web o foco escorregava para a mensagem de baixo, sempre na 6ª opção de 10.
		Causa, no código do NVDA 2026.2: a opção que entra na tela faz o WhatsApp
		rolar a lista do menu; o Chrome avisa "rolou" e o buffer
		(``gecko_ia2.event_scrollingStart`` → ``_handleScrollTo``) leva o cursor
		para o ponto rolado. Em modo foco, ``_set_selection`` então chama
		``setFocus`` no objeto focável desse ponto (browseMode.py:1952-1959), que
		era a mensagem atrás do menu, e o menu fechava. No aplicativo não há
		buffer, por isso lá não acontece. Com a trava ligada quem anda é o
		WhatsApp, então a rolagem não move nada. Em modo de navegação (NVDA+Espaço)
		a rolagem segue o NVDA.
		"""
		if self._wa_pinned and self.passThrough and self.isReady:
			try:
				where = diag.describe(obj)
			except Exception:
				where = "?"
			diag.act("rolagem-ignorada", "menu=%s %s" % (menu.active() is not None, where))
			return nextHandler()
		super().event_scrollingStart(obj, nextHandler)

	event_scrollingStart.ignoreIsReady = True

	# ─── pontos onde o NVDA compara com ``reportPassThrough.last`` ──────────

	def event_treeInterceptor_gainFocus(self):
		self._wa_update()
		self._wa_sync_last()
		super().event_treeInterceptor_gainFocus()

	def event_gainFocus(self, obj, nextHandler):
		self._wa_update()
		self._wa_sync_last()
		super().event_gainFocus(obj, nextHandler)

	# O gerenciador de eventos lê este atributo para entregar o evento mesmo
	# com o buffer ainda carregando (browseMode.py:161).
	event_gainFocus.ignoreIsReady = True


class WhatsAppWebDocument(chromium.Document):
	"""Sobreposição do documento raiz do WhatsApp Web: escolhe o buffer acima.

	O endereço é conferido DE NOVO na hora de escolher o buffer: o mesmo objeto
	de documento pode ter navegado para outro site depois de a sobreposição
	ser escolhida.
	"""

	def _get_treeInterceptorClass(self):
		cls = super().treeInterceptorClass
		if cls is ChromeVBuf and settings.scope_allows("web") and is_web_document(self):
			return WhatsAppChromeVBuf
		return cls
