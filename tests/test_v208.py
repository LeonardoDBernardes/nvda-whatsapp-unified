"""2.0.8: diagnostico para o relato do Leo de 31/10/2026 no WhatsApp Web.

O menu ainda escapava, tocava o som de troca de modo e a conversa ficava
"baguncada" depois; o log nao mostrou nada porque o limite de 200 linhas ja
tinha sido atingido. Agora o limite e maior e toda troca de modo no Web e as
setas de menu que ficam com o NVDA deixam uma linha.
"""

import logHandler
import pytest
from fakes import Gesture, Page, focus, message_menu

from globalPlugins.whatsAppUnified import GlobalPlugin, diag
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def lines(action):
	return [line for line in logHandler.log.lines if line.startswith("%s %s" % (diag.PREFIX, action))]


def web_page():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	focus(page.composer)
	return page, ti


def test_limit_is_large_enough_for_a_long_test_session():
	assert diag.MAX_LINES >= 3000


def test_every_mode_switch_by_nvda_in_the_web_is_logged():
	page, ti = web_page()
	ti.passThrough = False
	ti.passThrough = True
	found = lines("modo-trocou")
	assert any("para=navegacao" in line for line in found)
	assert any("para=foco" in line for line in found)


def test_add_on_own_silent_writes_are_not_logged_as_a_switch():
	page, ti = web_page()
	ti._passThrough = False
	assert lines("modo-trocou") == []


def test_menu_arrow_left_to_nvda_in_browse_mode_is_logged(plugin):
	page, ti = web_page()
	container, tray, items = message_menu()
	page.main.add(container)
	page.attach(ti)
	focus(items[0])
	plugin.event_gainFocus(items[0], lambda: None)
	ti._passThrough = False  # modo de navegacao dentro do menu
	assert plugin.getScript(Gesture("downArrow")) is None
	assert any("modo=navegacao" in line for line in lines("menu-seta-do-nvda"))
