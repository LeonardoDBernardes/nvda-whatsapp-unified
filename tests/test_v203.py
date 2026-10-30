"""2.0.3: relatos do Leo de 30/10/2026 sobre a 2.0.2.

- app e Web: com as setas o menu da mensagem "foge" para a mensagem de baixo ou de cima;
- Web: "Espaco e Esc me jogam nas reacoes; mais um Esc abre o menu";
- o Esc no menu faz o barulho do NVDA+Espaco.

Causa (codigo da pagina, 29/10/2026): pelo teclado o menu sao DOIS pop-ups, a barra de
reacoes (role menu so com botoes) e o menu de opcoes (menuitem). O foco vai para a barra;
o Esc num botao faz o NVDA trocar para o modo de navegacao (o som), e no modo de navegacao
as setas saem do menu.
"""

import api
import browseMode
import core
import keyboardHandler
import pytest
import speech
from controlTypes import OutputReason, Role, State
from fakes import Gesture, Node, Page, focus, inner_row

from globalPlugins.whatsAppUnified import GlobalPlugin, context, menu
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def real_page():
	page = Page(chats=0, messages=0)
	page.msg_rows = [inner_row("Fulano: mensagem %d" % i) for i in range(3)]
	for row in page.msg_rows:
		page.msg_list.add(row)
	return page


def open_real_menu(page, options=("Dados da mensagem", "Responder", "Copiar")):
	"""Os dois pop-ups do menu aberto pelo teclado, no fim do documento (portais)."""
	reactions = [Node(Role.TOGGLEBUTTON, r, states={State.FOCUSABLE}) for r in ("Curtir", "Amei", "Haha")]
	bar = Node(Role.POPUPMENU, "", children=reactions + [Node(Role.BUTTON, "Mais reações", states={State.FOCUSABLE})])
	items = [Node(Role.MENUITEM, o, states={State.FOCUSABLE}) for o in options]
	options_menu = Node(Role.POPUPMENU, "", children=items)
	page.doc.add(bar)
	page.doc.add(options_menu)
	return bar, reactions, options_menu, items


def deliver(plugin, obj):
	focus(obj)

	def next_handler():
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)


def start_on_message(plugin, page):
	deliver(plugin, page.msg_rows[0]._children[0])


def press(plugin, name):
	"""Aperta a tecla como o NVDA: script do add-on, se houver; senao a tecla segue (None)."""
	gesture = Gesture(name)
	script = plugin.getScript(gesture)
	if script is None:
		return None, gesture
	script(gesture)
	return script, gesture


def open_and_land(plugin, page):
	"""Espaco: o foco cai na barra; o add-on manda o Tab; o WhatsApp leva o foco a primeira opcao."""
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	deliver(plugin, reactions[0])
	core.run_pending()
	assert keyboardHandler.sent == ["tab"]
	deliver(plugin, items[0])  # o Tab do WhatsApp (onTabToMenu)
	return bar, reactions, options_menu, items


def after_grace(monkeypatch):
	"""O Esc de costume ja foi usado: o proximo Esc fecha o menu."""
	monkeypatch.setattr(menu._Menu, "habit_esc", False)


# ─── abrir: da barra de reacoes para as opcoes ──────────────────────────────

def test_opening_on_the_reaction_bar_goes_to_the_options_with_whatsapp_tab(plugin):
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	spoken = len(speech.spoken)
	deliver(plugin, reactions[0])
	assert menu.active() is bar and menu.in_tray()
	assert len(speech.spoken) == spoken  # a reacao nao e falada
	core.run_pending()
	assert keyboardHandler.sent == ["tab"]
	deliver(plugin, items[0])
	assert menu.active() is options_menu and not menu.in_tray()
	assert ("focus", items[0]) in speech.spoken


def test_no_tab_when_whatsapp_already_moved_the_focus(plugin):
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	deliver(plugin, reactions[0])
	deliver(plugin, items[0])  # o WhatsApp levou o foco sozinho antes do Tab
	core.run_pending()
	assert keyboardHandler.sent == []


def test_if_the_tab_does_not_move_the_reaction_is_spoken(plugin):
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	deliver(plugin, reactions[0])
	core.run_pending()  # Tab mandado, o foco nao andou
	assert any(kind == "object" and obj is reactions[0] for kind, obj, *_ in speech.spoken)


def test_option_off_stays_on_the_reactions(plugin):
	import config
	from globalPlugins.whatsAppUnified import settings

	config.conf[settings.CONFIG_SECTION]["menuStartOnOptions"] = False
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	deliver(plugin, reactions[0])
	core.run_pending()
	assert keyboardHandler.sent == []


# ─── setas: nunca saem do menu ──────────────────────────────────────────────

def test_arrows_go_to_whatsapp_and_stop_at_the_last(plugin):
	"""2.0.6: o add-on levava o foco com setFocus e o menu fechava perto do fim; agora a seta vai ao WhatsApp."""
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	keyboardHandler.sent.clear()
	for current in (items[0], items[1]):
		deliver(plugin, current)
		script, gesture = press(plugin, "downArrow")
		assert script is not None and gesture.sent == 1
	deliver(plugin, items[2])
	spoken = len(speech.spoken)
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 0 and keyboardHandler.sent == []
	assert all(item.focus_calls == 0 for item in items[1:])  # nenhum setFocus nas opcoes
	assert speech.spoken[spoken:] and speech.spoken[-1][1] is items[2]  # repete a ultima


def test_incomplete_list_never_blocks_the_arrow(plugin, monkeypatch):
	"""Lista de opcoes cortada pelo prazo: na duvida a seta vai ao WhatsApp."""
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	monkeypatch.setattr(menu, "items_state", lambda container: (items[:2], False))
	deliver(plugin, items[1])
	script, gesture = press(plugin, "downArrow")
	assert gesture.sent == 1


def test_down_on_the_reaction_bar_goes_to_the_options(plugin):
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	# o usuario voltou a barra de proposito (Shift+Tab): sem redirecionar
	deliver(plugin, items[0])
	deliver(plugin, reactions[1])
	core.run_pending()
	assert keyboardHandler.sent == []
	press(plugin, "downArrow")
	assert keyboardHandler.sent == ["tab"]


def test_up_on_the_first_option_goes_back_to_the_reaction_bar(plugin):
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	keyboardHandler.sent.clear()
	script, gesture = press(plugin, "upArrow")
	assert keyboardHandler.sent == ["shift+tab"] and gesture.sent == 0


def test_up_on_the_first_option_without_a_bar_stays_on_the_first(plugin):
	page = real_page()
	start_on_message(plugin, page)
	items = [Node(Role.MENUITEM, o, states={State.FOCUSABLE}) for o in ("A", "B", "C")]
	popup = Node(Role.POPUPMENU, "", children=items)
	page.doc.add(popup)
	deliver(plugin, items[0])
	script, gesture = press(plugin, "upArrow")
	assert gesture.sent == 0 and api.getFocusObject() is items[0]
	assert keyboardHandler.sent == []


# ─── Esc: vai para o WhatsApp, sem som e sem modo de navegacao ──────────────

def test_escape_in_the_menu_goes_to_whatsapp_without_sound_in_the_web(plugin, monkeypatch):
	page = real_page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	page.attach(ti)
	after_grace(monkeypatch)
	sounds = list(browseMode.sounds)
	script, gesture = press(plugin, "escape")
	assert script is not None
	assert gesture.sent == 1  # o WhatsApp recebe o Esc e fecha o menu
	assert ti.passThrough is True  # continua em modo foco
	assert browseMode.sounds == sounds  # nenhum som


def test_escape_on_the_reaction_bar_also_goes_to_whatsapp(plugin, monkeypatch):
	page = real_page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	page.attach(ti)
	deliver(plugin, items[0])
	deliver(plugin, reactions[0])  # voltou a barra de proposito
	after_grace(monkeypatch)
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1 and ti.passThrough is True


def test_escape_in_the_app_menu_goes_to_whatsapp(plugin, monkeypatch):
	page = real_page()  # sem buffer, como no aplicativo
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	after_grace(monkeypatch)
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1


def test_habit_escape_right_after_opening_keeps_the_menu_open(plugin):
	"""O costume do Leo, "Espaco e depois Esc": o primeiro Esc logo depois de abrir nao fecha."""
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	spoken = len(speech.spoken)
	script, gesture = press(plugin, "escape")
	assert script is not None and gesture.sent == 0
	assert speech.spoken[spoken:] and speech.spoken[-1][1] is items[0]  # repete a opcao
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1  # o segundo Esc fecha


def test_habit_escape_has_no_time_limit(plugin):
	"""2.0.4: o Leo aperta Espaco e depois Esc em sequencia; so a ordem das teclas conta, nao o tempo."""
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 0
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1


def test_after_the_menu_closes_escape_is_native_again(plugin):
	"""Depois de fechado, o Esc seguinte e o de sempre (volta para a lista de conversas)."""
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	press(plugin, "escape")  # costume
	press(plugin, "escape")  # fecha
	page.doc.remove(bar)
	page.doc.remove(options_menu)
	start_on_message(plugin, page)
	assert menu.active() is None
	assert plugin.getScript(Gesture("escape")) is None


def test_habit_escape_while_still_on_the_bar_is_swallowed(plugin):
	page = real_page()
	start_on_message(plugin, page)
	bar, reactions, options_menu, items = open_real_menu(page)
	deliver(plugin, reactions[0])
	script, gesture = press(plugin, "escape")  # antes do Tab do add-on
	assert gesture.sent == 0


def test_after_an_arrow_escape_closes_right_away(plugin):
	page = real_page()
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	press(plugin, "downArrow")
	deliver(plugin, items[1])
	script, gesture = press(plugin, "escape")
	assert gesture.sent == 1


def test_escape_outside_a_menu_is_nvda_own(plugin):
	page = real_page()
	start_on_message(plugin, page)
	assert plugin.getScript(Gesture("escape")) is None


def test_escape_in_browse_mode_is_nvda_own(plugin):
	page = real_page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	bar, reactions, options_menu, items = open_and_land(plugin, page)
	page.attach(ti)
	ti._passThrough = False
	assert plugin.getScript(Gesture("escape")) is None


def test_menu_focus_in_browse_mode_goes_back_to_focus_mode_in_the_web(plugin):
	page = real_page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	start_on_message(plugin, page)
	ti.script_disablePassThrough(Gesture("escape"))  # Esc fora do menu: modo de navegacao
	assert ti.passThrough is False
	bar, reactions, options_menu, items = open_real_menu(page)
	page.attach(ti)
	deliver(plugin, items[0])
	assert ti.shouldPassThrough(items[0], OutputReason.FOCUS) is True


# ─── mensagem reconhecida sem procurar o campo de digitacao ──────────────────

def test_message_div_gets_its_class_without_searching_the_page(plugin, monkeypatch):
	from fakes import apply_overlays
	from globalPlugins.whatsAppUnified import tree
	from globalPlugins.whatsAppUnified.overlays import MessageRow

	page = real_page()
	start_on_message(plugin, page)
	context.forget_kinds()
	monkeypatch.setattr(tree, "iter_children", lambda *a, **k: pytest.fail("varreu filhos"))
	target = page.msg_rows[1]._children[0]
	focus(target)
	apply_overlays(target, {"web"})
	assert isinstance(target, MessageRow)
