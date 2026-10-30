"""Objetos falsos do NVDA e uma pagina do WhatsApp Web montada com eles."""

import itertools

import api
import speech
import winUser
from controlTypes import Role, State
from NVDAObjects.IAccessible import IAccessible, chromium

_ids = itertools.count(1)
_hwnds = itertools.count(1000)


class ComLog:
	"""Conta o acesso ao "COM" dos objetos falsos (pai, filhos, vizinhos, IAccessibleObject, accValue)."""

	active = False
	calls = []

	@classmethod
	def start(cls):
		cls.calls = []
		cls.active = True

	@classmethod
	def stop(cls):
		cls.active = False
		return list(cls.calls)

	@classmethod
	def note(cls, what):
		if cls.active:
			cls.calls.append(what)


class FakeApp:
	def __init__(self, appName, isWhatsAppUnified=False):
		self.appName = appName
		if isWhatsAppUnified:
			self.isWhatsAppUnified = True


class FakeAccessible:
	def __init__(self, url):
		self.url = url

	def accValue(self, child):
		ComLog.note("accValue")
		if self.url is None:
			raise OSError("sem endereco")
		return self.url


class Node(IAccessible):
	"""Um objeto de acessibilidade com pai, filhos e acoes registradas."""

	def __init__(self, role, name="", states=(), children=(), app=None, hwnd=100, focusable=True, value=""):
		self.role = role
		self.name = name
		self.states = set(states)
		self._parent = None
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

	@property
	def parent(self):
		ComLog.note("parent")
		return self._parent

	@parent.setter
	def parent(self, value):
		self._parent = value

	@property
	def IAccessibleObject(self):
		ComLog.note("IAccessibleObject")
		if getattr(self, "_iao", None) is None:
			raise AttributeError("IAccessibleObject")
		return self._iao

	@IAccessibleObject.setter
	def IAccessibleObject(self, value):
		self._iao = value

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
			node = node._parent  # o NVDA conhece o programa pelo processo: nao e COM
		return None

	@property
	def firstChild(self):
		ComLog.note("firstChild")
		return self._children[0] if self._children else None

	@property
	def lastChild(self):
		ComLog.note("lastChild")
		return self._children[-1] if self._children else None

	def _sibling(self, step):
		ComLog.note("sibling")
		if self._parent is None:
			return None
		siblings = self._parent._children
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


def inner_row(name, selected=False, buttons=("Menu",)):
	"""Estrutura real (29/10/2026): linha (TABLEROW) que NAO aceita foco > div focavel (SECTION)
	com o texto + fileira de botoes de acao. O foco do NVDA fica no div, nao na linha."""
	states = {State.FOCUSABLE}
	if selected:
		states.add(State.SELECTED)
	inner = Node(Role.SECTION, name, states=states, children=[Node(Role.STATICTEXT, name)])
	children = [inner] + [Node(Role.BUTTON, label) for label in buttons]
	return Node(Role.TABLEROW, name, children=children, focusable=False)


def message_menu(options=("Responder", "Copiar", "Apagar"), reactions=("Curtir", "Amei")):
	"""Menu antigo da mensagem (WAWebDropdown): application > lista > [reacoes, separador, opcoes]."""
	tray = Node(Role.SECTION, "", children=[Node(Role.BUTTON, r, states={State.FOCUSABLE}) for r in reactions])
	items = [Node(Role.BUTTON, o, states={State.FOCUSABLE}) for o in options]
	listing = Node(Role.LIST, "", children=[tray, Node(Role.SEPARATOR, "")] + items)
	return Node(Role.APPLICATION, "", children=[listing]), tray, items


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

	def attach(self, ti):
		"""O buffer (tree interceptor) do documento: como no NVDA, todo objeto da pagina o encontra."""
		def walk(node):
			node.treeInterceptor = ti
			for child in node._children:
				walk(child)

		walk(self.doc)
		return ti

	def overlay_all(self, contexts=frozenset({"web"})):
		focus(self.composer)  # o evento de foco ja confirmou o WhatsApp Web
		for row in self.chat_rows + self.msg_rows:
			apply_overlays(row, contexts)
		return self


def focus(obj, event=True):
	"""Poe o foco no objeto.

	``event=True`` imita o que o plugin global faz na primeira linha do evento de
	foco (``context.update_focus``). ``event=False``: foco do NVDA mudou, mas o
	evento ainda nao chegou ao add-on.
	"""
	api.setFocusObject(obj)
	if event:
		from globalPlugins.whatsAppUnified import context

		context.update_focus(obj)
	return obj
