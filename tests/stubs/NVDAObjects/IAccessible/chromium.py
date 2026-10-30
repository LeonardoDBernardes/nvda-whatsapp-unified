"""Stub de chromium.py: Document escolhe o ChromeVBuf; ChromeVBuf le o endereco como o NVDA (accValue(0))."""

import browseMode
from NVDAObjects.IAccessible import IAccessible


class ChromeVBuf(browseMode.BrowseModeDocumentTreeInterceptor):
	def __init__(self, rootNVDAObject):
		super().__init__(rootNVDAObject)

	def _get_documentConstantIdentifier(self):
		try:
			return self.rootNVDAObject.IAccessibleObject.accValue(0)
		except Exception:
			return None


class Document(IAccessible):
	def _get_treeInterceptorClass(self):
		return ChromeVBuf
