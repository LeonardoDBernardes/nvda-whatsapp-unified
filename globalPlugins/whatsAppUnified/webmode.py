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

SOLUÇÃO (a opção (a) do roteiro, a mesma que o próprio NVDA usa no MSHTML,
virtualBuffers/MSHTML.py:241-250, e no Excel): uma subclasse do buffer do
Chromium, ``WhatsAppChromeVBuf``, escolhida por sobreposição do documento
(``WhatsAppWebDocument._get_treeInterceptorClass``). Ela
1. NASCE em modo foco: ``_passThrough = True`` e ``_disableAutoPassThrough = True``
   (privados de propósito: o setter público chamaria
   ``_focusLastFocusableObject`` e puxaria o foco do usuário; o MSHTML faz igual);
2. sincroniza ``reportPassThrough.last`` com o modo dela ao nascer, ao ganhar
   o foco e a cada evento de foco. Assim entrar no documento é SILENCIOSO;
3. responde SEMPRE a mesma coisa em ``shouldPassThrough(obj, FOCUS|CARET)``
   enquanto o modo foco está fixado (True). Sem resposta variável não há troca
   de modo; sem troca de modo ``reportPassThrough`` nunca toca.

O QUE CONTINUA NATIVO:
- NVDA+Espaço (``script_toggleVirtualBufferPassThrough``) alterna normalmente e
  toca o som, porque o ``.last`` está sincronizado com o modo anterior. A escolha
  do Leo vale: em modo de navegação (``disableAutoPassThrough`` falso) a classe
  devolve False, exceto em campo de texto editável (o NVDA já faz isso), e volta a
  ficar em modo foco quando ele alterna de novo;
- Escape: com ``disableAutoPassThrough`` verdadeiro o script nativo
  ``script_disablePassThrough`` repassa a tecla à página (fecha conversa, etc.)
  em vez de sair do modo foco. Sem isso o Escape tocaria o som de navegação;
- outros sites: a sobreposição só vale se o endereço do documento é
  ``*.whatsapp.com``; qualquer outro documento usa o ChromeVBuf original.

LIMITES (documentados no README): vale para o Chromium com IAccessible2, que é o
padrão do NVDA (``allowInChromium = 0``). Se o usuário ligou UI Automation para
navegadores baseados em Chromium, o buffer não é um ChromeVBuf e nada aqui roda.
Sair do WhatsApp para uma página em modo de navegação pode tocar UM som, o
mesmo que o NVDA toca ao mudar de modo entre documentos.
"""

import browseMode
import controlTypes
from controlTypes import OutputReason
from NVDAObjects.IAccessible import chromium
from NVDAObjects.IAccessible.chromium import ChromeVBuf

from . import settings
from .context import url_is_whatsapp, web_title_hint


def editable_and_available(obj):
	"""Campo de texto editável e disponível (a regra nativa de entrada de texto)."""
	try:
		states = obj.states
	except Exception:
		return False
	return controlTypes.State.EDITABLE in states and controlTypes.State.UNAVAILABLE not in states


class WhatsAppChromeVBuf(ChromeVBuf):
	"""Buffer do Chromium para documentos do WhatsApp Web, em modo foco fixo."""

	_wa_decided = False  # o veredito (WhatsApp ou não) já saiu do endereço?
	_wa_verdict = None  # True/False quando decidido; lido por context._is_web_whatsapp
	_wa_pinned = False  # modo foco fixado por esta classe

	def __init__(self, rootNVDAObject):
		super().__init__(rootNVDAObject)
		self._wa_update()

	# ─── veredito e fixação do modo foco ────────────────────────────────────

	def _wa_is_whatsapp(self):
		if self._wa_decided:
			return bool(self._wa_verdict)
		try:
			verdict = url_is_whatsapp(self.documentConstantIdentifier)
		except Exception:
			verdict = None
		if verdict is None:
			# Sem endereço utilizável ainda: o título é a reserva e não fica guardado.
			return web_title_hint(self.rootNVDAObject)
		self._wa_decided = True
		self._wa_verdict = verdict
		return verdict

	def _wa_enabled(self):
		return settings.scope_allows("web") and bool(settings.get("autoFocusMode"))

	def _wa_update(self):
		"""Fixa o modo foco uma única vez, quando o documento é o WhatsApp Web."""
		if self._wa_pinned:
			return
		if self._wa_is_whatsapp() and self._wa_enabled():
			self._wa_pinned = True
			self._wa_decided = True
			self._wa_verdict = True
			self._disableAutoPassThrough = True
			self._passThrough = True
			browseMode.reportPassThrough.last = True

	def _wa_sync_last(self):
		"""Faz o "último modo anunciado" do NVDA coincidir com o deste documento."""
		if self._wa_pinned:
			browseMode.reportPassThrough.last = self.passThrough

	# ─── decisão de modo ─────────────────────────────────────────────────────

	def shouldPassThrough(self, obj, reason=None):
		if reason in (OutputReason.FOCUS, OutputReason.CARET) and self._wa_pinned and self._wa_enabled():
			if self.disableAutoPassThrough:
				# Modo foco fixado: SEMPRE a mesma resposta, para qualquer objeto.
				return True
			# O Leo escolheu o modo de navegação (NVDA+Espaço): respeita, e só
			# entra em modo foco em campo de texto, como o NVDA faz.
			return editable_and_available(obj)
		return super().shouldPassThrough(obj, reason)

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
	"""Sobreposição do documento raiz do WhatsApp Web: escolhe o buffer acima."""

	def _get_treeInterceptorClass(self):
		cls = super().treeInterceptorClass
		if cls is ChromeVBuf and settings.scope_allows("web"):
			return WhatsAppChromeVBuf
		return cls
