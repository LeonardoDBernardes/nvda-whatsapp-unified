"""Stub de chromium.py: Document escolhe o ChromeVBuf; ChromeVBuf le o endereco como o NVDA (accValue(0))."""

import api
import browseMode
from NVDAObjects.IAccessible import IAccessible


class ChromeVBuf(browseMode.BrowseModeDocumentTreeInterceptor):
	def __init__(self, rootNVDAObject):
		super().__init__(rootNVDAObject)

	def event_scrollingStart(self, obj, nextHandler):
		"""gecko_ia2.event_scrollingStart + _handleScrollTo + _set_selection (browseMode.py:1946-1959)."""
		if not self.isReady:
			return nextHandler()
		self.scrolledTo = obj
		self.passThrough = self.shouldPassThrough(obj, reason=browseMode.OutputReason.CARET)
		if self.passThrough and obj is not api.getFocusObject() and obj.isFocusable:
			obj.setFocus()

	event_scrollingStart.ignoreIsReady = True

	def _get_documentConstantIdentifier(self):
		try:
			return self.rootNVDAObject.IAccessibleObject.accValue(0)
		except Exception:
			return None


class Document(IAccessible):
	def _get_treeInterceptorClass(self):
		return ChromeVBuf
