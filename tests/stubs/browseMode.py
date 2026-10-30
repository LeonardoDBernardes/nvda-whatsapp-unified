"""Stub FIEL de browseMode.py do NVDA 2026.2 (so o necessario para o som de troca de modo).

Cada trecho abaixo copia a logica do codigo-fonte do NVDA e diz de onde veio, para o teste
reproduzir o comportamento real:
- reportPassThrough: browseMode.py:56-78 (toca focusMode.wav / browseMode.wav quando o modo
  difere da variavel GLOBAL ``reportPassThrough.last``);
- shouldPassThrough: browseMode.py:366-433;
- event_gainFocus (trecho que decide o modo): browseMode.py:2131-2224 e _set_selection:1951-1961;
- event_treeInterceptor_gainFocus: browseMode.py:1835-1892;
- script_disablePassThrough: browseMode.py:762-771;
- toggle_pass_through: globalCommands.py:2527-2564 (NVDA+Espaco).
"""

import api
import config
import controlTypes
from baseObject import AutoPropertyObject
from controlTypes import OutputReason

sounds = []  # arquivos de som que o NVDA tocaria, em ordem
calls = []  # toda chamada a reportPassThrough: (modo, onlyIfChanged)


class _Reporter:
	"""reportPassThrough do NVDA. ``writes`` guarda toda escrita EXTERNA em ``.last`` (as do add-on)."""

	def __init__(self):
		self._last = False
		self.writes = []

	@property
	def last(self):
		return self._last

	@last.setter
	def last(self, value):
		self.writes.append(value)
		self._last = value

	def __call__(self, treeInterceptor, onlyIfChanged=True):
		calls.append((treeInterceptor.passThrough, onlyIfChanged))
		if not onlyIfChanged or treeInterceptor.passThrough != self._last:
			if config.conf["virtualBuffers"]["passThroughAudioIndication"]:
				sounds.append("focusMode.wav" if treeInterceptor.passThrough else "browseMode.wav")
			self._last = treeInterceptor.passThrough  # escrita do proprio NVDA: nao entra em ``writes``


reportPassThrough = _Reporter()


def reset():
	sounds.clear()
	calls.clear()
	reportPassThrough._last = False
	reportPassThrough.writes.clear()


class BrowseModeTreeInterceptor(AutoPropertyObject):
	_disableAutoPassThrough = False
	IGNORE_DISABLE_PASS_THROUGH_WHEN_FOCUSED_ROLES = frozenset()

	ALWAYS_SWITCH_TO_PASS_THROUGH_ROLES = frozenset(
		{
			controlTypes.Role.COMBOBOX,
			controlTypes.Role.EDITABLETEXT,
			controlTypes.Role.LIST,
			controlTypes.Role.RADIOMENUITEM,
			controlTypes.Role.CHECKMENUITEM,
			controlTypes.Role.TABLECELL,
		},
	)
	SWITCH_TO_PASS_THROUGH_ON_FOCUS_ROLES = frozenset(
		{
			controlTypes.Role.LISTITEM,
			controlTypes.Role.RADIOBUTTON,
			controlTypes.Role.TAB,
			controlTypes.Role.MENUITEM,
			controlTypes.Role.RADIOMENUITEM,
			controlTypes.Role.CHECKMENUITEM,
		},
	)

	_passThrough = False

	def _get_passThrough(self):
		return self._passThrough

	def _set_passThrough(self, state):
		if self._passThrough == state:
			return
		self._passThrough = state
		self.passThroughChanges.append(state)

	def _get_disableAutoPassThrough(self):
		return self._disableAutoPassThrough

	def _set_disableAutoPassThrough(self, state):
		self._disableAutoPassThrough = state

	def event_treeInterceptor_gainFocus(self):
		reportPassThrough(self)

	def shouldPassThrough(self, obj, reason=None):
		if reason and (
			self.disableAutoPassThrough
			or (
				reason == OutputReason.FOCUS
				and not config.conf["virtualBuffers"]["autoPassThroughOnFocusChange"]
			)
			or (
				reason == OutputReason.CARET
				and not config.conf["virtualBuffers"]["autoPassThroughOnCaretMove"]
			)
		):
			return self.passThrough
		if reason == OutputReason.QUICKNAV:
			return False
		states = obj.states
		role = obj.role
		if controlTypes.State.EDITABLE in states and controlTypes.State.UNAVAILABLE not in states:
			return True
		if (
			not obj.isFocusable
			and controlTypes.State.FOCUSED not in states
			and role != controlTypes.Role.POPUPMENU
		):
			return False
		if controlTypes.State.READONLY in states:
			if (
				role == controlTypes.Role.LISTITEM
				and controlTypes.State.FOCUSED in states
				and obj.parent.role == controlTypes.Role.LIST
				and controlTypes.State.FOCUSABLE in obj.parent.states
			):
				return True
			if role not in (
				controlTypes.Role.EDITABLETEXT,
				controlTypes.Role.COMBOBOX,
				controlTypes.Role.TABLEROW,
				controlTypes.Role.TABLECELL,
				controlTypes.Role.TABLEROWHEADER,
				controlTypes.Role.TABLECOLUMNHEADER,
			):
				return False
		if role in self.ALWAYS_SWITCH_TO_PASS_THROUGH_ROLES or controlTypes.State.EDITABLE in states:
			return True
		if reason == OutputReason.FOCUS:
			if role in self.SWITCH_TO_PASS_THROUGH_ON_FOCUS_ROLES:
				return True
			while obj and obj != self.rootNVDAObject:
				if obj.role == controlTypes.Role.TOOLBAR:
					return True
				obj = obj.parent
		return False

	def script_disablePassThrough(self, gesture):
		if not self.passThrough or self.disableAutoPassThrough:
			return gesture.send()
		self.passThrough = False
		self.disableAutoPassThrough = False
		reportPassThrough(self)

	script_disablePassThrough.ignoreTreeInterceptorPassThrough = True


def toggle_pass_through(vbuf):
	"""NVDA+Espaco (globalCommands.script_toggleVirtualBufferPassThrough, trecho do buffer existente)."""
	vbuf.passThrough = not vbuf.passThrough
	vbuf.disableAutoPassThrough = vbuf.passThrough
	reportPassThrough(vbuf)


class BrowseModeDocumentTreeInterceptor(BrowseModeTreeInterceptor):
	isReady = True

	def __init__(self, rootNVDAObject):
		self.rootNVDAObject = rootNVDAObject
		self._passThrough = False
		self._disableAutoPassThrough = False
		self.passThroughChanges = []
		self._hadFirstGainFocus = False
		self._lastFocusObj = None
		self._enteringFromOutside = False

	def _set_selection_for(self, obj, reason):
		"""Trecho de ``_set_selection`` que decide o modo e enfileira o aviso (browseMode.py:1951-1961)."""
		self.passThrough = self.shouldPassThrough(obj, reason=reason)
		reportPassThrough(self)

	def event_gainFocus(self, obj, nextHandler):
		self._enteringFromOutside = False
		if not self.isReady:
			if self.passThrough:
				nextHandler()
			return
		if obj == self.rootNVDAObject:
			if self.passThrough:
				return nextHandler()
			return
		self._lastFocusObj = obj
		passThrough = self.shouldPassThrough(obj, reason=OutputReason.FOCUS)
		self.passThrough = passThrough
		if self.passThrough:
			nextHandler()
		self._set_selection_for(obj, OutputReason.FOCUS)

	event_gainFocus.ignoreIsReady = True

	def event_treeInterceptor_gainFocus(self):
		hadFirstGainFocus = self._hadFirstGainFocus
		if not hadFirstGainFocus:
			focus = api.getFocusObject()
			self.event_gainFocus(focus, lambda: focus.event_gainFocus())
			if not self.passThrough:
				reportPassThrough(self)
			self._hadFirstGainFocus = True
		reportPassThrough(self)
