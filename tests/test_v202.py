"""2.0.2: relatos do Leo de 30/10/2026 (setas revistas na 2.0.6: vao para o WhatsApp).

- a mensagem real e uma linha (TABLEROW) que nao aceita foco com um div focavel (SECTION)
  dentro; o foco do NVDA fica no div. A 2.0.1 so reconhecia a linha, entao os comandos da
  mensagem nao valiam;
- o menu da mensagem agora comeca com a fileira de reacoes e o foco caia nela;
- descendo pelas opcoes do menu, o foco escorregava para a mensagem de baixo.
"""

import api
import config
import core
import pytest
import speech
from controlTypes import Role, State
from fakes import Gesture, Node, Page, apply_overlays, focus, inner_row, message_menu

from globalPlugins.whatsAppUnified import GlobalPlugin, menu, settings
from globalPlugins.whatsAppUnified.overlays import ChatListRow, MessageRow
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def real_page(messages=3, chats=3):
	"""Pagina do WhatsApp Web com linhas no formato real (div focavel dentro da linha)."""
	page = Page(chats=0, messages=0)
	page.chat_rows = [inner_row("Conversa %d" % i, selected=(i == 1), buttons=()) for i in range(chats)]
	for row in page.chat_rows:
		page.chat_list.add(row)
	page.msg_rows = [inner_row("Fulano: mensagem %d" % i) for i in range(messages)]
	for row in page.msg_rows:
		page.msg_list.add(row)
	return page


def inner(row):
	return row._children[0]


def deliver(plugin, obj):
	focus(obj)
	calls = []

	def next_handler():
		calls.append(obj)
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)
	return calls


# ─── a mensagem e o div focavel dentro da linha ──────────────────────────────

def test_inner_message_div_gets_the_message_overlay_and_knows_its_row():
	page = real_page()
	focus(page.composer)
	target = inner(page.msg_rows[0])
	focus(target)
	apply_overlays(target, {"web"})
	assert isinstance(target, MessageRow)
	assert target.wa_row is page.msg_rows[0]


def test_inner_chat_div_gets_the_chat_overlay():
	page = real_page()
	focus(page.composer)
	target = inner(page.chat_rows[0])
	focus(target)
	apply_overlays(target, {"web"})
	assert isinstance(target, ChatListRow)


def test_copy_from_the_inner_div_copies_the_message_text():
	page = real_page()
	focus(page.composer)
	target = inner(page.msg_rows[1])
	focus(target)
	apply_overlays(target, {"web"})
	target.script_copyMessage(Gesture("control+c"))
	assert api.clipboard == ["Fulano: mensagem 1"]


def test_context_menu_from_the_inner_div_clicks_the_row_menu_button():
	page = real_page()
	focus(page.composer)
	target = inner(page.msg_rows[0])
	focus(target)
	apply_overlays(target, {"web"})
	target.script_contextMenu(Gesture("applications"))
	assert page.msg_rows[0]._children[1].actions == [0]


def test_alt_2_focuses_the_inner_div_of_the_last_message(plugin):
	page = real_page()
	focus(page.composer)
	plugin.script_goToMessageList(Gesture("alt+2"))
	assert inner(page.msg_rows[-1]).focus_calls == 1
	assert page.msg_rows[-1].focus_calls == 0


# ─── menu da mensagem ────────────────────────────────────────────────────────

def open_menu(page):
	container, tray, items = message_menu()
	page.main.add(container)
	return container, tray, items


def test_menu_opening_on_a_reaction_goes_to_the_first_option_without_speaking_the_reaction(plugin):
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	reaction = tray._children[0]
	spoken_before = len(speech.spoken)
	calls = deliver(plugin, reaction)
	assert calls == [reaction]  # o NVDA recebeu o evento (o buffer fica em dia)
	assert len(speech.spoken) == spoken_before  # mas a reacao nao foi falada
	assert items[0].focus_calls == 1
	assert api.getFocusObject() is items[0]
	assert menu.active() is container


def test_if_whatsapp_refuses_the_move_the_reaction_is_spoken_after_a_moment(plugin):
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	reaction = tray._children[0]
	items[0].setFocus = lambda: None  # o WhatsApp nao aceitou o foco
	deliver(plugin, reaction)
	core.run_pending()
	assert any(kind == "object" and obj is reaction for kind, obj, *_ in speech.spoken)


def test_option_off_keeps_whatsapp_choice(plugin):
	config.conf[settings.CONFIG_SECTION]["menuStartOnOptions"] = False
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	deliver(plugin, tray._children[0])
	assert items[0].focus_calls == 0
	assert menu.active() is container  # as setas continuam do add-on


def test_down_and_up_arrows_go_to_whatsapp_and_up_on_the_first_goes_to_the_reactions(plugin):
	"""2.0.6: quem anda pelas opcoes e o proprio WhatsApp; o add-on so age nas pontas."""
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	deliver(plugin, items[0])
	down = Gesture("downArrow")
	script = plugin.getScript(down)
	assert script is not None
	script(down)
	assert down.sent == 1 and items[1].focus_calls == 0  # a seta foi para o WhatsApp
	deliver(plugin, items[2])
	down = Gesture("downArrow")
	plugin.getScript(down)(down)
	assert down.sent == 0 and api.getFocusObject() is items[2]  # para na ultima, sem dar a volta
	deliver(plugin, items[0])
	up = Gesture("upArrow")
	plugin.getScript(up)(up)
	assert api.getFocusObject() is tray._children[0]  # reagir continua possivel
	assert up.sent == 0


def test_arrows_belong_to_nvda_outside_a_menu(plugin):
	page = real_page()
	focus(page.composer)
	deliver(plugin, inner(page.msg_rows[0]))
	assert menu.active() is None
	assert plugin.getScript(Gesture("downArrow")) is None


def test_arrows_belong_to_nvda_in_browse_mode(plugin):
	page = real_page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	focus(page.composer)
	container, tray, items = open_menu(page)
	page.attach(ti)
	deliver(plugin, items[0])
	assert plugin.getScript(Gesture("downArrow")) is not None  # modo foco: do add-on
	ti._passThrough = False  # Leo apertou Esc: modo de navegacao
	assert plugin.getScript(Gesture("downArrow")) is None


def test_arrows_belong_to_a_text_field_inside_the_menu(plugin):
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	search = Node(Role.EDITABLETEXT, "Pesquisar", states={State.FOCUSABLE, State.EDITABLE})
	container._children[0].add(search)
	deliver(plugin, search)
	assert menu.active() is container
	assert plugin.getScript(Gesture("downArrow")) is None


def test_new_menu_with_menu_items(plugin):
	page = real_page()
	focus(page.composer)
	items = [Node(Role.MENUITEM, n, states={State.FOCUSABLE}) for n in ("Responder", "Copiar")]
	popup = Node(Role.POPUPMENU, "", children=items)
	page.main.add(popup)
	deliver(plugin, popup)  # o NVDA pos o foco no conteiner
	assert api.getFocusObject() is items[0]
	deliver(plugin, items[0])
	down = Gesture("downArrow")
	plugin.getScript(down)(down)
	assert down.sent == 1  # o WhatsApp anda


def test_leaving_the_menu_releases_the_arrows(plugin):
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	deliver(plugin, items[0])
	assert menu.active() is container
	page.main.remove(container)
	deliver(plugin, inner(page.msg_rows[0]))
	assert menu.active() is None


def test_menu_without_buffer_also_gets_the_arrows(plugin):
	"""Sem buffer (como no aplicativo) o mesmo menu vale: o foco nao escorrega para a mensagem."""
	page = real_page()
	focus(page.composer)
	container, tray, items = open_menu(page)
	deliver(plugin, items[1])
	assert items[1].treeInterceptor is None
	down = Gesture("downArrow")
	plugin.getScript(down)(down)
	assert down.sent == 1
	deliver(plugin, items[2])
	down = Gesture("downArrow")
	plugin.getScript(down)(down)
	assert down.sent == 0  # na ultima opcao: para
