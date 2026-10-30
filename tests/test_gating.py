"""getScript: a tecla so e nossa dentro do WhatsApp e dentro do escopo; fora, segue intacta."""

import config
import pytest
from controlTypes import Role
from fakes import FakeApp, Gesture, Node, Page, focus
from scriptHandler import script

from globalPlugins.whatsAppUnified import GlobalPlugin, settings

OUR_KEYS = ["alt+1", "alt+2", "alt+d", "shift+alt+c", "control+shift+e", "nvda+shift+h"]
NOT_OURS = ["nvda+space", "nvda+shift+i", "escape", "control+v", "alt+tab", "nvda+t"]


@pytest.fixture
def plugin():
	return GlobalPlugin()


@pytest.mark.parametrize("key", OUR_KEYS)
def test_our_keys_work_inside_whatsapp_web(plugin, key):
	page = Page()
	focus(page.composer)
	assert plugin.getScript(Gesture(key)) is not None


@pytest.mark.parametrize("key", OUR_KEYS)
def test_our_keys_fall_through_outside_whatsapp(plugin, key):
	other = Page(url="https://www.example.com/")
	focus(other.composer)
	assert plugin.getScript(Gesture(key)) is None


@pytest.mark.parametrize("key", OUR_KEYS)
def test_our_keys_fall_through_in_unrelated_apps(plugin, key):
	focus(Node(Role.EDITABLETEXT, "x", app=FakeApp("notepad")))
	assert plugin.getScript(Gesture(key)) is None


@pytest.mark.parametrize("key", NOT_OURS)
def test_native_keys_are_never_swallowed(plugin, key):
	page = Page()
	focus(page.composer)
	assert plugin.getScript(Gesture(key)) is None
	focus(Node(Role.EDITABLETEXT, "x", app=FakeApp("notepad")))
	assert plugin.getScript(Gesture(key)) is None


def test_scope_desktop_blocks_web(plugin):
	config.conf[settings.CONFIG_SECTION]["scope"] = "desktop"
	page = Page()
	focus(page.composer)
	assert plugin.getScript(Gesture("alt+1")) is None
	app = Node(Role.EDITABLETEXT, "x", app=FakeApp("whatsapp.root", isWhatsAppUnified=True))
	focus(app)
	assert plugin.getScript(Gesture("alt+1")) is not None


def test_scope_web_blocks_app(plugin):
	config.conf[settings.CONFIG_SECTION]["scope"] = "web"
	app = Node(Role.EDITABLETEXT, "x", app=FakeApp("whatsapp.root", isWhatsAppUnified=True))
	focus(app)
	assert plugin.getScript(Gesture("alt+1")) is None
	page = Page()
	focus(page.composer)
	assert plugin.getScript(Gesture("alt+1")) is not None


def test_no_focus_object_does_not_raise(plugin):
	assert plugin.getScript(Gesture("alt+1")) is None


def test_message_row_keys_only_on_message_rows():
	page = Page().overlay_all()
	focus(page.msg_rows[0])
	for key in ("alt+enter", "alt+c", "control+r", "control+c", "shift+enter", "control+shift+enter"):
		assert page.msg_rows[0].getScript(Gesture(key)) is not None, key
	assert page.chat_rows[0].getScript(Gesture("control+c")) is None
	assert page.msg_rows[0].getScript(Gesture("nvda+space")) is None


class NativeBinding:
	"""Uma classe NATIVA do NVDA com script na mesma tecla (Ctrl+C) que a linha usa."""

	@script(description="nativo", gesture="kb:control+c")
	def script_nativeCopy(self, gesture):
		return "nativo"


def row_with_native_binding(page):
	from globalPlugins.whatsAppUnified import overlays

	row = page.msg_rows[0]
	row.__class__ = type(type(row))("ForcedRow", (overlays.MessageRow, NativeBinding, type(row)), {})
	row.initOverlayClass()
	return row


def test_message_row_outside_its_scope_returns_what_nvda_would_return_without_the_addon():
	"""Fora do escopo a linha devolve o script NATIVO da mesma tecla, nao None."""
	page = Page()
	row = row_with_native_binding(page)
	config.conf[settings.CONFIG_SECTION]["scope"] = "desktop"  # o web saiu do escopo
	script_found = row.getScript(Gesture("control+c"))
	assert script_found is not None and script_found.__name__ == "script_nativeCopy"
	config.conf[settings.CONFIG_SECTION]["scope"] = "both"
	assert row.getScript(Gesture("control+c")).__name__ == "script_copyMessage"


def test_message_row_gestures_are_not_bound_on_the_class():
	"""Se estivessem ligados na classe, esconderiam o nativo mesmo devolvendo None."""
	from globalPlugins.whatsAppUnified import overlays

	for name in dir(overlays.MessageRow):
		if name.startswith("script_"):
			assert not getattr(getattr(overlays.MessageRow, name), "wa_gestures", ())


class ExplodingNode(Node):
	"""Qualquer caminhada pelos filhos falha: prova que a decisao da tecla nao anda pela arvore."""

	@property
	def firstChild(self):
		raise AssertionError("caminhada pela arvore na decisao da tecla")

	@property
	def lastChild(self):
		raise AssertionError("caminhada pela arvore na decisao da tecla")


def test_message_row_get_script_never_walks_the_tree():
	from globalPlugins.whatsAppUnified import overlays

	page = Page()
	row = ExplodingNode(Role.TABLEROW, "Fulano: oi", states=set())
	page.msg_list.add(row)
	row.__class__ = type(type(row))("ForcedRow", (overlays.MessageRow, type(row)), {})
	row.initOverlayClass()
	for key in ("enter", "alt+p", "control+s", "shift+enter", "control+shift+enter", "control+r", "alt+enter", "alt+c", "control+c"):
		found = row.getScript(Gesture(key))
		assert found is not None, key
	assert row.getScript(Gesture("nvda+space")) is None


def test_enter_alt_p_ctrl_s_decide_inside_the_script_and_pass_the_key_when_there_is_no_player():
	page = Page().overlay_all()
	row = page.msg_rows[0]
	focus(row)
	for key, name in (("enter", "script_playMessage"), ("alt+p", "script_audioToggle"), ("control+s", "script_audioSpeed")):
		gesture = Gesture(key)
		found = row.getScript(gesture)
		assert found.__name__ == name  # o script existe sempre
		found(gesture)
		assert gesture.sent == 1, key  # sem player: a tecla segue para a pagina
	play = Node(Role.BUTTON, "Reproduzir mensagem de voz")
	speed = Node(Role.BUTTON, "1x")
	slider = Node(Role.SLIDER, "posicao")
	for item in (speed, play, slider):
		row.add(item)
	gesture = Gesture("enter")
	row.getScript(gesture)(gesture)
	assert play.actions == [0] and gesture.sent == 0
	gesture = Gesture("control+s")
	row.getScript(gesture)(gesture)
	assert speed.actions == [0] and gesture.sent == 0
	gesture = Gesture("alt+p")
	row.getScript(gesture)(gesture)
	assert play.actions == [0, 0] and gesture.sent == 0


def test_ctrl_c_with_selected_text_goes_to_the_page():
	import api

	page = Page().overlay_all()
	row = page.msg_rows[0]
	focus(row)

	class Info:
		def __init__(self, collapsed):
			self.isCollapsed = collapsed

	row.makeTextInfo = lambda position: Info(False)
	gesture = Gesture("control+c")
	row.getScript(gesture)(gesture)
	assert gesture.sent == 1 and api.clipboard == []
	row.makeTextInfo = lambda position: Info(True)
	gesture = Gesture("control+c")
	row.getScript(gesture)(gesture)
	assert gesture.sent == 0 and api.clipboard == ["Fulano: mensagem 0"]


def test_ctrl_c_selection_in_the_tree_interceptor_also_counts():
	import api

	page = Page().overlay_all()
	row = page.msg_rows[0]

	class Info:
		isCollapsed = False

	class Holder:
		def makeTextInfo(self, position):
			return Info()

	row.treeInterceptor = Holder()
	gesture = Gesture("control+c")
	row.getScript(gesture)(gesture)
	assert gesture.sent == 1 and api.clipboard == []


def test_global_plugin_binds_only_its_own_documented_keys():
	"""O mapa do plugin so tem os nossos comandos (conferido no fonte: quem devolve None e ignorado)."""
	bound = set()
	for name in dir(GlobalPlugin):
		if name.startswith("script_"):
			bound.update(getattr(getattr(GlobalPlugin, name), "wa_gestures", ()))
	assert bound == {"kb:alt+1", "kb:alt+2", "kb:alt+d", "kb:shift+alt+c", "kb:control+shift+e", "kb:nvda+shift+h"}
