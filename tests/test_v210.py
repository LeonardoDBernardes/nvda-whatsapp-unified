"""2.0.10: relato do Leo de 31/10/2026 no WhatsApp Web.

Descendo pelas opcoes do menu da mensagem, o foco escorregava para a mensagem de
baixo (sempre na 6a opcao de 10). A opcao que entra na tela faz a lista do menu
rolar; o buffer do NVDA seguia a rolagem e punha o foco na mensagem atras do
menu. Com o modo foco travado a rolagem nao move nada.
"""

import api
import browseMode
import logHandler
import pytest
from fakes import Gesture, Page, focus, message_menu

from globalPlugins.whatsAppUnified import GlobalPlugin, diag, menu
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def lines(action):
	return [line for line in logHandler.log.lines if line.startswith("%s %s" % (diag.PREFIX, action))]


def deliver(plugin, obj):
	focus(obj)
	plugin.event_gainFocus(obj, obj.reportFocus)


def web_menu(plugin):
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	focus(page.composer)
	container, tray, items = message_menu(options=tuple("Opcao %d" % i for i in range(10)))
	page.main.add(container)
	page.attach(ti)
	deliver(plugin, items[5])
	return page, ti, items


def test_scroll_while_going_down_the_menu_keeps_the_focus_on_the_option(plugin):
	page, ti, items = web_menu(plugin)
	assert menu.active() is not None and ti.passThrough
	message = page.msg_rows[-1]
	before = message.focus_calls
	passed = []
	ti.event_scrollingStart(message, lambda: passed.append(True))
	assert message.focus_calls == before  # a mensagem atras do menu nao ganhou o foco
	assert api.getFocusObject() is items[5]
	assert passed == [True]  # o evento segue para o objeto, como o NVDA faz sem buffer
	assert lines("rolagem-ignorada")


def test_scroll_in_focus_mode_outside_a_menu_also_keeps_the_focus(plugin):
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	focus(page.composer)
	message = page.msg_rows[0]
	ti.event_scrollingStart(message, lambda: None)
	assert message.focus_calls == 0
	assert api.getFocusObject() is page.composer


def test_scroll_in_browse_mode_is_nvda_own(plugin):
	page, ti, items = web_menu(plugin)
	browseMode.toggle_pass_through(ti)  # NVDA+Espaco: modo de navegacao
	assert ti.passThrough is False
	message = page.msg_rows[-1]
	ti.event_scrollingStart(message, lambda: None)
	assert ti.scrolledTo is message  # o cursor do NVDA segue a rolagem


def test_down_arrow_still_goes_to_whatsapp_on_the_web(plugin):
	page, ti, items = web_menu(plugin)
	down = Gesture("downArrow")
	plugin.getScript(down)(down)
	assert down.sent == 1
