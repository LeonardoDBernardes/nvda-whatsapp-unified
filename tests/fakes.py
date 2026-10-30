"""Objetos falsos do NVDA e uma pagina do WhatsApp Web montada com eles."""

import itertools

import api
import speech
import winUser
from controlTypes import Role, State
from NVDAObjects.IAccessible import IAccessible, chromium

_ids = itertools.count(1)
_hwnds = itertools.count(1000)


class FakeApp:
	def __init__(self, appName, isWhatsAppUnified=False):
		self.appName = appName
		if isWhatsAppUnified:
			self.isWhatsAppUnified = True


class FakeAccessible:
	def __init__(self, url):
		self.url = url

	def accValue(self, child):
		if self.url is None:
			raise OSError("sem endereco")
		return self.url


class Node(IAccessible):
	"""Um objeto de acessibilidade com pai, filhos e acoes registradas."""

	def __init__(self, role, name="", states=(), children=(), app=None, hwnd=100, focusable=True, value=""):
		self.role = role
		self.name = name
		self.states = set(states)
		self.parent = None
		self._children = []
		self._app = app
		self.windowHandle = hwnd
		self.windowClassName = "Chrome_RenderWidgetHostHWND"
		self.IA2UniqueID = next(_ids)
		self.isFocusable = focusable
		self.treeInterceptor = None
		self.value = value
		self.actions = []
		self.on_action = None
		self.focus_calls = 0
		self.positionInfo = {}
		self.location = None
		for child in children:
			self.add(child)

	def _set_hwnd(self, hwnd):
		self.windowHandle = hwnd
		for child in self._children:
			child._set_hwnd(hwnd)

	def add(self, child):
		child.parent = self
		self._children.append(child)
		child._set_hwnd(self.windowHandle)  # uma pagina = uma janela (cada aba tem a sua)
		return child

	def remove(self, child):
		self._children.remove(child)
		child.parent = None

	@property
	def appModule(self):
		node = self
		while node is not None:
			if node._app is not None:
				return node._app
			node = node.parent
		return None

	@property
	def firstChild(self):
		return self._children[0] if self._children else None

	@property
	def lastChild(self):
		return self._children[-1] if self._children else None

	def _sibling(self, step):
		if self.parent is None:
			return None
		siblings = self.parent._children
		index = siblings.index(self) + step
		return siblings[index] if 0 <= index < len(siblings) else None

	@property
	def next(self):
		return self._sibling(1)

	@property
	def previous(self):
		return self._sibling(-1)

	def setFocus(self):
		self.focus_calls += 1
		api.setFocusObject(self)

	def doAction(self, index=0):
		self.actions.append(index)
		if self.on_action is not None:
			self.on_action()

	def reportFocus(self):
		speech.spoken.append(("focus", self))

	def event_gainFocus(self):
		pass


class DocNode(Node, chromium.Document):
	"""A raiz do documento: devolve o endereco como o IAccessible2 do Chromium."""

	def __init__(self, url, **kwargs):
		super().__init__(Role.DOCUMENT, name="WhatsApp", **kwargs)
		self.IAccessibleObject = FakeAccessible(url)


class Gesture:
	def __init__(self, ident):
		from inputCore import normalizeGestureIdentifier

		self.identifiers = ("kb:" + ident.lower(),)
		self.normalizedIdentifiers = (normalizeGestureIdentifier("kb:" + ident),)
		self.sent = 0

	def send(self):
		self.sent += 1


def apply_overlays(obj, contexts):
	"""Imita o NVDA: monta a lista de classes e mistura as sobreposicoes ao objeto."""
	from globalPlugins.whatsAppUnified import overlays

	cls_list = [chromium.Document] if isinstance(obj, chromium.Document) else []
	overlays.choose_overlay_classes(obj, cls_list, contexts)
	extra = tuple(c for c in cls_list if not isinstance(obj, c))
	if extra:
		meta = type(type(obj))
		obj.__class__ = meta("Overlaid" + type(obj).__name__, extra + (type(obj),), {})
		obj.initOverlayClass()
	return cls_list


def chat_row(name, selected=False):
	states = {State.FOCUSABLE}
	if selected:
		states.add(State.SELECTED)
	cell = Node(Role.TABLECELL, name, children=[Node(Role.BUTTON, name + " botao")])
	return Node(Role.TABLEROW, name, states=states, children=[cell])


def message_row(name, extra=()):
	children = [Node(Role.STATICTEXT, name), Node(Role.BUTTON, "Menu")]
	children.extend(extra)
	return Node(Role.TABLEROW, name, states={State.FOCUSABLE}, children=children)


class Page:
	"""document > [lateral(lista de conversas), principal(cabecalho, mensagens, campo de digitacao)]."""

	def __init__(self, url="https://web.whatsapp.com/", app_name="chrome", chats=3, messages=3, title=None):
		if title is None:
			title = "(2) WhatsApp - Google Chrome" if "whatsapp" in str(url) else "Exemplo - Google Chrome"
		hwnd = next(_hwnds)
		winUser.setTitle(hwnd, title)
		winUser.setTitle(1, title)
		self.app = FakeApp(app_name)
		self.doc = DocNode(url, app=self.app, hwnd=hwnd)
		self.chat_rows = [chat_row("Conversa %d" % i, selected=(i == 1)) for i in range(chats)]
		self.chat_list = Node(Role.TABLE, "Lista de conversas", states={State.FOCUSABLE}, children=self.chat_rows)
		side = Node(Role.SECTION, "", children=[self.chat_list])
		self.call_button = Node(Role.BUTTON, "Chamada de voz")
		self.msg_rows = [message_row("Fulano: mensagem %d" % i) for i in range(messages)]
		self.msg_list = Node(Role.TABLE, "", states={State.FOCUSABLE}, children=self.msg_rows)
		self.composer = Node(
			Role.EDITABLETEXT,
			"Digite uma mensagem",
			states={State.FOCUSABLE, State.EDITABLE, State.MULTILINE},
		)
		self.main = Node(Role.SECTION, "", children=[self.call_button, self.msg_list, self.composer])
		self.doc.add(side)
		self.doc.add(self.main)

	def overlay_all(self, contexts=frozenset({"web"})):
		for row in self.chat_rows + self.msg_rows:
			apply_overlays(row, contexts)
		return self


def focus(obj):
	"""Poe o foco no objeto (sem gerar evento)."""
	api.setFocusObject(obj)
	return obj
