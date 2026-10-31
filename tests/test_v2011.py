"""2.0.11: relato do Leo de 31/10/2026 no WhatsApp Web ("ele ainda foge").

Descendo pelas opcoes do menu da mensagem, o foco escorregava para a mensagem de
baixo, sempre na 6a opcao de 10. Causa (codigo da pagina, useWDSMenu): com o
menu aberto o WhatsApp fecha o menu em qualquer rolagem fora dele, e a opcao
fora da parte visivel da janela faz o Chrome rolar a pagina ao ganhar o foco.
Agora, so no Web, a opcao fora da tela e falada sem mover o foco.
"""

import api
import browseMode
import keyboardHandler
import logHandler
import pytest
import speech
from controlTypes import OutputReason, Role, State
from fakes import FakeApp, Gesture, Node, Page, focus, inner_row

from globalPlugins.whatsAppUnified import GlobalPlugin, context, diag, menu
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf

VISIBLE = 5  # como na tela do Leo: 5 das 10 opcoes cabem na janela
ITEM_HEIGHT = 40
MENU_TOP = 400
VIEW_HEIGHT = MENU_TOP + VISIBLE * ITEM_HEIGHT


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def lines(action):
	"""Linhas do diagnostico desta acao (exata: "menu-virtual" nao conta "menu-virtual-fim")."""
	start = diag.PREFIX + " "
	return [line for line in logHandler.log.lines if line.startswith(start) and line[len(start):].split(" ")[0] == action]


def deliver(plugin, obj):
	focus(obj)

	def next_handler():
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)


def press(plugin, name):
	"""Aperta a tecla como o NVDA: script do add-on, se houver; senao a tecla segue (None)."""
	gesture = Gesture(name)
	script = plugin.getScript(gesture)
	if script is None:
		return None, gesture
	script(gesture)
	return script, gesture


def menu_page(plugin, offscreen_state=True, app=False):
	"""Pagina com o menu de opcoes (10) que passa da borda de baixo da janela.

	O foco ja esta na 5a opcao (a ultima visivel), como no log do Leo. Com
	``offscreen_state`` o Chrome marca "fora da tela" as opcoes de baixo; sem
	ele so a posicao diz que elas passam da janela.
	"""
	page = Page(chats=0, messages=0)
	if app:
		page.doc._app = FakeApp("whatsapp.root", isWhatsAppUnified=True)
	page.doc.location = (0, 0, 800, VIEW_HEIGHT)
	page.msg_rows = [inner_row("Fulano: mensagem %d" % i) for i in range(3)]
	for row in page.msg_rows:
		page.msg_list.add(row)
	items = []
	for i in range(10):
		states = {State.FOCUSABLE}
		if offscreen_state and i >= VISIBLE:
			states.add(State.OFFSCREEN)
		item = Node(Role.MENUITEM, "Opcao %d" % (i + 1), states=states)
		item.location = (100, MENU_TOP + i * ITEM_HEIGHT, 200, ITEM_HEIGHT)
		items.append(item)
	options_menu = Node(Role.POPUPMENU, "", children=items)
	page.doc.add(options_menu)
	ti = None
	if not app:
		ti = WhatsAppChromeVBuf(page.doc)
		page.attach(ti)
	deliver(plugin, page.msg_rows[0]._children[0])
	for item in items[:VISIBLE]:  # o WhatsApp levou o foco pelas opcoes visiveis
		deliver(plugin, item)
	menu._Menu.habit_esc = False
	keyboardHandler.sent.clear()
	speech.spoken.clear()
	return page, ti, items


def spoken_objects():
	return [entry[1] for entry in speech.spoken if entry[0] == "object"]


def test_the_page_really_puts_the_lower_options_outside_the_window(plugin):
	page, ti, items = menu_page(plugin)
	assert context.active() == "web" and ti.passThrough
	top = items[VISIBLE - 1].location[1]
	assert top + ITEM_HEIGHT == VIEW_HEIGHT  # a 5a opcao termina na borda
	assert items[VISIBLE].location[1] >= VIEW_HEIGHT  # a 6a ja passou


def test_down_to_an_option_outside_the_window_speaks_it_without_moving_the_focus(plugin):
	page, ti, items = menu_page(plugin)
	script, gesture = press(plugin, "downArrow")
	assert script is not None and gesture.sent == 0  # a seta nao vai ao WhatsApp: nada rola
	assert api.getFocusObject() is items[VISIBLE - 1]
	assert items[VISIBLE].focus_calls == 0
	assert spoken_objects() == [items[VISIBLE]]
	assert speech.spoken[-1][2] == OutputReason.FOCUS
	assert menu.virtual_item() is items[VISIBLE]
	assert lines("menu-virtual")


def test_virtual_navigation_stops_on_the_last_option(plugin):
	page, ti, items = menu_page(plugin)
	for _ in range(10):
		script, gesture = press(plugin, "downArrow")
		assert gesture.sent == 0
	assert menu.virtual_item() is items[-1]
	assert spoken_objects()[-1] is items[-1]  # ficou na ultima e a repetiu
	assert lines("menu-ponta")
	assert all(item.focus_calls == 0 for item in items[VISIBLE:])


def test_up_comes_back_to_the_option_with_the_focus(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	press(plugin, "downArrow")
	assert menu.virtual_item() is items[VISIBLE + 1]
	script, gesture = press(plugin, "upArrow")
	assert gesture.sent == 0 and menu.virtual_item() is items[VISIBLE]
	script, gesture = press(plugin, "upArrow")
	assert gesture.sent == 0
	assert menu.virtual_item() is None  # de volta a opcao com o foco
	assert spoken_objects()[-1] is items[VISIBLE - 1]
	script, gesture = press(plugin, "upArrow")
	assert gesture.sent == 1  # opcao visivel: a seta e do WhatsApp de novo


def test_enter_activates_the_spoken_option(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	press(plugin, "downArrow")
	script, gesture = press(plugin, "enter")
	assert script is not None and gesture.sent == 0
	assert items[VISIBLE + 1].actions == [0]
	assert items[VISIBLE - 1].actions == []  # nunca a opcao onde o foco esta
	assert menu.virtual_item() is None
	assert lines("menu-virtual-ativar")


def test_space_activates_the_spoken_option(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	script, gesture = press(plugin, "space")
	assert script is not None and gesture.sent == 0
	assert items[VISIBLE].actions == [0]


def test_failed_activation_never_sends_the_key(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")

	def broken(index=0):
		raise OSError("sem acao")

	items[VISIBLE].doAction = broken
	script, gesture = press(plugin, "enter")
	assert gesture.sent == 0  # o Enter ativaria a opcao com o foco, nao a falada
	assert lines("menu-virtual-falhou")


def test_enter_and_space_are_whatsapp_own_on_visible_options(plugin):
	page, ti, items = menu_page(plugin)
	for name in ("enter", "space", "numpadEnter"):
		script, gesture = press(plugin, name)
		assert script is None, name


def test_escape_during_virtual_navigation_closes_the_menu(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1 and ti.passThrough is True
	assert menu.virtual_item() is None


def test_focus_moving_ends_the_virtual_navigation(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	deliver(plugin, page.msg_rows[0]._children[0])  # o menu fechou e o foco voltou a mensagem
	assert menu.virtual_item() is None
	script, gesture = press(plugin, "enter")
	assert script is None


def test_browse_mode_keeps_enter_with_nvda(plugin):
	page, ti, items = menu_page(plugin)
	press(plugin, "downArrow")
	browseMode.toggle_pass_through(ti)  # NVDA+Espaco: modo de navegacao
	assert ti.passThrough is False
	script, gesture = press(plugin, "enter")
	assert script is None


def test_position_alone_also_detects_the_option_outside_the_window(plugin):
	page, ti, items = menu_page(plugin, offscreen_state=False)
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 0 and menu.virtual_item() is items[VISIBLE]


def test_option_cut_by_the_window_edge_is_outside(plugin):
	page, ti, items = menu_page(plugin, offscreen_state=False)
	left, top, width, height = items[VISIBLE].location
	items[VISIBLE].location = (left, VIEW_HEIGHT - 10, width, 10)  # o Chrome encolhe a parte escondida
	page.doc.location = (0, 0, 800, VIEW_HEIGHT + 10)
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 0 and menu.virtual_item() is items[VISIBLE]


def test_visible_options_still_go_to_whatsapp(plugin):
	page, ti, items = menu_page(plugin)
	deliver(plugin, items[2])
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 1 and menu.virtual_item() is None


def test_unknown_position_goes_to_whatsapp_as_before(plugin):
	page, ti, items = menu_page(plugin, offscreen_state=False)
	for item in items:
		item.location = None
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 1 and menu.virtual_item() is None


def test_the_app_is_untouched(plugin):
	"""No aplicativo a janela cabe o menu inteiro: a seta sempre vai ao WhatsApp, como na 2.0.7."""
	page, ti, items = menu_page(plugin, app=True)
	assert context.active() == "app"
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 1 and menu.virtual_item() is None
	script, gesture = press(plugin, "enter")
	assert script is None
