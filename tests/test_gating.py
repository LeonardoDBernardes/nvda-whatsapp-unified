"""getScript: a tecla so e nossa dentro do WhatsApp e dentro do escopo; fora, segue intacta."""

import config
import pytest
from controlTypes import Role
from fakes import FakeApp, Gesture, Node, Page, focus

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


def test_message_row_keys_fall_through_outside_whatsapp():
	other = Page(url="https://www.example.com/")
	row = other.msg_rows[0]
	from globalPlugins.whatsAppUnified import overlays

	row.__class__ = type(type(row))("Forced", (overlays.MessageRow, type(row)), {})
	focus(row)
	assert row.getScript(Gesture("control+c")) is None


def test_enter_alt_p_ctrl_s_only_when_the_message_has_a_player():
	from controlTypes import Role
	from fakes import Node

	page = Page().overlay_all()
	row = page.msg_rows[0]
	focus(row)
	for key in ("enter", "alt+p", "control+s"):
		assert row.getScript(Gesture(key)) is None, key  # sem player: a tecla e da pagina
	play = Node(Role.BUTTON, "Reproduzir mensagem de voz")
	speed = Node(Role.BUTTON, "1x")
	slider = Node(Role.SLIDER, "posicao")
	for item in (speed, play, slider):
		row.add(item)
	for key in ("enter", "alt+p", "control+s"):
		assert row.getScript(Gesture(key)) is not None, key
	row.script_playMessage(Gesture("enter"))
	assert play.actions == [0]
	row.script_audioSpeed(Gesture("control+s"))
	assert speed.actions == [0]
	row.script_audioToggle(Gesture("alt+p"))
	assert play.actions == [0, 0]
