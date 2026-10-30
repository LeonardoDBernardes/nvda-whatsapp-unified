"""Filtros de fala, Ctrl+C, 'ler mais' e comandos da mensagem."""

import api
import config
import core
import keyboardHandler
import ui
from controlTypes import Role
from fakes import Gesture, Node, Page, focus

from globalPlugins.whatsAppUnified import filters, messagetext, settings

PHONE = "+55 11 91234-5678"


def option(key, value):
	config.conf[settings.CONFIG_SECTION][key] = value


# ─── filtros ────────────────────────────────────────────────────────────────

HINT = "Para mais opções, pressione a seta para a direita."


def test_phone_in_chat_list_names_only_when_the_option_is_on():
	text = "Maria %s enviou foto" % PHONE
	assert filters.filter_text(text, "chat") == text  # padrao: desligado na lista de conversas
	option("filterChatList", True)
	assert PHONE not in filters.filter_text(text, "chat")


def test_phone_in_messages_only_as_the_sender_prefix():
	assert filters.filter_text("%s: oi, tudo bem?" % PHONE, "message") == "oi, tudo bem?"
	body = "Maria: ligue para %s amanhã" % PHONE
	assert filters.filter_text(body, "message") == body  # no corpo: nunca
	assert filters.filter_text("Maria: %s" % PHONE, "message") == "Maria: %s" % PHONE
	option("filterMessageList", False)
	assert filters.filter_text("%s: oi" % PHONE, "message") == "%s: oi" % PHONE


def test_phone_inside_a_message_body_keeps_its_meaning():
	body = "Anote: o código é %s e vale hoje" % PHONE
	assert filters.filter_text(body, "message") == body


def test_unknown_kind_is_never_touched():
	text = "Talvez Ana %s. %s" % (PHONE, HINT)
	assert filters.filter_text(text, None) == text
	assert filters.filter_text(text, "button") == text


def test_usage_hint_item_alone_is_dropped_but_ok_and_fragments_stay():
	assert filters.filter_item(HINT, "message", "Fulano: oi") == ""
	assert filters.filter_item("ok", "message", "Fulano: oi") == "ok"
	assert filters.filter_item("menu", "message", "Fulano: oi") == "menu"
	assert filters.filter_item("Para mais informações", "message", "Fulano: oi") == "Para mais informações"
	option("filterUsageHints", False)
	assert filters.filter_item(HINT, "message", "Fulano: oi") == HINT


def test_usage_hint_is_cut_from_the_end_of_a_chat_name_only():
	name = "Maria, disse oi. " + HINT
	assert filters.filter_text(name, "chat") == "Maria, disse oi."
	# Dentro de uma mensagem o texto e do usuario: nunca se corta.
	message = "Ana: " + "Para mais opções, pressione a seta para a direita."
	assert filters.filter_text(message, "message") == message
	middle = "Maria: veja Para mais opções, pressione a seta e depois responda"
	assert filters.filter_text(middle, "chat") == middle  # no meio: nao e frase final


def test_ordinary_sentences_that_resemble_hints_stay():
	normal = "Para mais opções de pagamento ligue amanhã"
	assert filters.filter_text(normal, "chat") == normal
	assert filters.filter_item(normal, "chat", "outro nome") == normal


def test_talvez_prefix_only_on_chat_names_and_message_senders():
	assert filters.filter_text("Talvez João Silva", "chat") == "João Silva"
	assert filters.filter_text("Talvez João Silva: oi", "message") == "João Silva: oi"
	option("filterTalvez", False)
	assert filters.filter_text("Talvez João Silva", "chat") == "Talvez João Silva"


def test_talvez_inside_a_message_body_is_untouched():
	for body in ("Talvez amanhã eu vá", "Maria: Talvez amanhã", "Maria: sim. Talvez João: oi"):
		assert filters.filter_text(body, "message") == body, body
	assert filters.filter_text("Ele disse Talvez amanhã", "chat") == "Ele disse Talvez amanhã"


def test_line_breaks_are_preserved():
	option("filterChatList", True)
	text = "Talvez Ana  %s\nOntem,  10:30\n\nfoto" % PHONE
	out = filters.filter_text(text, "chat")
	assert out == "Ana \nOntem, 10:30\n\nfoto"
	assert out.count("\n") == 3


def test_empty_text_passes():
	assert filters.filter_text("", "chat") == ""
	assert filters.filter_text(None, "chat") is None


def test_speech_filter_touches_only_the_name_of_the_focused_row():
	page = Page().overlay_all()
	row = page.msg_rows[0]
	row.name = "%s: disse oi" % PHONE
	focus(row)
	seq = [row.name, object(), "ok", "Fulano %s no corpo" % PHONE]
	out = filters.on_speech_sequence(seq)
	assert out[0] == "disse oi"
	assert out[1] is seq[1] and out[2] == "ok"
	assert out[3] == seq[3]  # outro texto: intacto


def test_speech_filter_ignores_everything_outside_rows_and_whatsapp():
	page = Page().overlay_all()
	focus(page.composer)  # campo de digitacao: eco de digitacao nunca e filtrado
	seq = ["Talvez", "%s" % PHONE, HINT]
	assert filters.on_speech_sequence(seq) is seq
	focus(page.msg_rows[0].lastChild)  # botao dentro da linha
	assert filters.on_speech_sequence(seq) is seq
	other = Page(url="https://www.example.com/")
	focus(other.composer)
	assert filters.on_speech_sequence(seq) is seq


def test_speech_filter_uses_the_kind_of_the_focused_row():
	page = Page().overlay_all()
	row = page.chat_rows[0]
	row.name = "Talvez Ana %s" % PHONE
	focus(row)
	out = filters.on_speech_sequence([row.name])
	assert out == ["Ana %s" % PHONE]  # telefone na lista de conversas fica (padrao)


def test_speech_filter_drops_a_hint_item_that_is_the_whole_sentence():
	page = Page().overlay_all()
	focus(page.msg_rows[0])
	assert filters.on_speech_sequence([page.msg_rows[0].name, HINT]) == [page.msg_rows[0].name]


def test_speech_filter_never_raises():
	api.setFocusObject(None)
	seq = ["a"]
	assert filters.on_speech_sequence(seq) is seq


# ─── Ctrl+C ─────────────────────────────────────────────────────────────────

def test_ctrl_c_copies_and_speaks_copiado():
	page = Page().overlay_all()
	row = page.msg_rows[0]
	focus(row)
	gesture = Gesture("control+c")
	row.getScript(gesture)(gesture)
	assert api.clipboard == ["Fulano: mensagem 0"]
	assert ui.messages == ["Copiado"]
	assert gesture.sent == 0


def test_ctrl_c_without_text_goes_to_the_page():
	page = Page().overlay_all()
	empty = Node(Role.TABLEROW, "", states=set(), children=[Node(Role.BUTTON, "Menu")])
	page.msg_list.add(empty)
	from fakes import apply_overlays

	apply_overlays(empty, {"web"})
	gesture = Gesture("control+c")
	empty.script_copyMessage(gesture)
	assert gesture.sent == 1 and api.clipboard == [] and ui.messages == []


# ─── "Ler mais" ─────────────────────────────────────────────────────────────

def truncated_row():
	static = Node(Role.STATICTEXT, "Era uma vez")
	button = Node(Role.BUTTON, "Ler mais")
	row = Node(Role.TABLEROW, "Era uma vez… Ler mais", children=[static, button])
	return row, static, button


def test_read_more_polls_until_the_text_grows():
	row, static, button = truncated_row()
	got = []
	messagetext.expand_then(row, got.append)
	assert button.actions == [0] and got == []
	assert core.pending[0][0] == messagetext.EXPAND_DELAY_MS
	core.run_pending(limit=1)  # 60 ms: ainda igual
	core.run_pending(limit=1)  # 120 ms: ainda igual
	assert got == []
	static.name = "Era uma vez um texto bem maior depois de expandir"
	row.name = ""
	core.run_pending(limit=1)
	assert got == ["Era uma vez um texto bem maior depois de expandir"]
	assert core.pending == []  # parou de conferir


def test_read_more_delivers_what_it_has_after_the_deadline():
	row, _static, _button = truncated_row()
	got = []
	messagetext.expand_then(row, got.append)
	core.run_pending()
	assert len(got) == 1 and got[0] == "Era uma vez"
	assert core.pending == []


def test_read_more_is_checked_21_times_at_most():
	row, _static, _button = truncated_row()
	messagetext.expand_then(row, lambda text: None)
	count = core.run_pending()
	assert count == messagetext.EXPAND_MAX_TRIES + 1


def test_without_read_more_button_delivers_at_once():
	row = Node(Role.TABLEROW, "mensagem curta", children=[Node(Role.STATICTEXT, "mensagem curta")])
	got = []
	messagetext.expand_then(row, got.append)
	assert got == ["mensagem curta"] and core.pending == []


def test_vanished_button_does_not_break():
	row, _static, button = truncated_row()

	def boom():
		raise RuntimeError("sumiu")

	button.on_action = boom
	got = []
	messagetext.expand_then(row, got.append)
	assert got == ["Era uma vez"] and core.pending == []


def test_ctrl_r_reads_the_expanded_text():
	page = Page().overlay_all()
	static = Node(Role.STATICTEXT, "Inicio")
	button = Node(Role.BUTTON, "Ler mais")
	row = Node(Role.TABLEROW, "Inicio… Ler mais", children=[static, button])
	page.msg_list.add(row)
	from fakes import apply_overlays

	apply_overlays(row, {"web"})
	focus(row)
	row.script_readFull(Gesture("control+r"))
	static.name = "Inicio e todo o resto do texto"
	row.name = ""
	core.run_pending()
	assert ui.messages == ["Inicio e todo o resto do texto"]


# ─── Outros comandos ────────────────────────────────────────────────────────

def test_shift_enter_without_menu_button_sends_applications_key():
	page = Page().overlay_all()
	row = page.msg_rows[0]
	row.firstChild.next.name = "Outro"  # nenhum botao de menu
	row.script_contextMenu(Gesture("shift+enter"))
	assert keyboardHandler.sent == ["applications"]


def test_shift_enter_clicks_the_menu_button():
	page = Page().overlay_all()
	row = page.msg_rows[0]
	row.script_contextMenu(Gesture("shift+enter"))
	assert row.lastChild.actions == [0] and keyboardHandler.sent == []


def test_react_without_button_says_so():
	page = Page().overlay_all()
	page.msg_rows[0].script_reactMessage(Gesture("control+shift+enter"))
	assert ui.messages == ["Botão de reação não encontrado"]


def test_call_button_missing_says_so_and_present_clicks():
	from globalPlugins.whatsAppUnified import GlobalPlugin

	plugin = GlobalPlugin()
	page = Page()
	page.main.remove(page.call_button)
	focus(page.composer)
	plugin.script_openCallMenu(Gesture("shift+alt+c"))
	assert ui.messages == ["Botão de chamada não encontrado"]
	page.main.add(page.call_button)
	plugin.script_openCallMenu(Gesture("shift+alt+c"))
	assert page.call_button.actions == [0]


def test_navigation_commands_focus_the_right_places():
	from globalPlugins.whatsAppUnified import GlobalPlugin

	plugin = GlobalPlugin()
	page = Page()
	focus(page.composer)
	plugin.script_goToChatList(Gesture("alt+1"))
	assert page.chat_rows[1].focus_calls == 1  # a selecionada
	plugin.script_goToMessageList(Gesture("alt+2"))
	assert page.msg_rows[-1].focus_calls == 1  # a ultima mensagem
	plugin.script_focusComposer(Gesture("alt+d"))
	assert page.composer.focus_calls == 1


def test_toggles_flip_the_options_and_speak():
	from globalPlugins.whatsAppUnified import GlobalPlugin

	plugin = GlobalPlugin()
	plugin.script_togglePhoneFilter(Gesture("control+shift+e"))
	assert settings.get("filterMessageList") is False
	assert ui.messages[-1] == "Filtro de telefone desativado"
	plugin.script_toggleHintsFilter(Gesture("nvda+shift+h"))
	assert settings.get("filterUsageHints") is False
	assert ui.messages[-1] == "Filtro de dicas desativado"
