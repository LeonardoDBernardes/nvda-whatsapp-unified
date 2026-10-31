"""2.0.7: relato do Leo de 31/10/2026 — ler a mensagem palavra por palavra com Ctrl+setas.

Na 1.4 dava; na 2.0 o aplicativo nao tem modo de navegacao e o Web fica em modo foco,
entao a tecla ia para o WhatsApp, que nao faz nada com ela no div da mensagem.
"""

import speech
from fakes import Gesture, Page, apply_overlays, focus, inner_row

from globalPlugins.whatsAppUnified import overlays
from globalPlugins.whatsAppUnified.overlays import MessageRow


def message(text):
	"""Mensagem do Web; o aplicativo usa a mesma classe MessageRow e o mesmo script."""
	page = Page(chats=0, messages=0)
	row = inner_row(text)
	page.msg_list.add(row)
	focus(page.composer)
	target = row._children[0]
	focus(target)
	apply_overlays(target, {"web"})
	assert isinstance(target, MessageRow)
	return target


def press(target, name):
	gesture = Gesture(name)
	script = target.getScript(gesture)
	assert script is not None
	speech.spoken.clear()
	script(gesture)
	return gesture, list(speech.spoken)


def test_ctrl_right_reads_word_by_word_and_stops_at_the_last():
	target = message("Oi, tudo bem?")
	assert press(target, "control+rightArrow")[1] == [("text", "Oi,")]
	assert press(target, "control+rightArrow")[1] == [("text", "tudo")]
	assert press(target, "control+rightArrow")[1] == [("text", "bem?")]
	gesture, spoken = press(target, "control+rightArrow")
	assert spoken == [("text", "bem?")] and gesture.sent == 0  # para na ultima, nao sai da mensagem


def test_ctrl_left_goes_back_and_stops_at_the_first():
	target = message("um dois tres")
	press(target, "control+rightArrow")
	press(target, "control+rightArrow")
	assert press(target, "control+leftArrow")[1] == [("text", "um")]
	assert press(target, "control+leftArrow")[1] == [("text", "um")]


def test_one_character_word_is_spelled():
	target = message("a b")
	assert press(target, "control+rightArrow")[1] == [("spelling", "a")]


def test_other_message_starts_from_the_first_word():
	first = message("primeira mensagem")
	press(first, "control+rightArrow")
	press(first, "control+rightArrow")
	second = message("segunda mensagem")
	assert press(second, "control+rightArrow")[1] == [("text", "segunda")]


def test_message_without_text_lets_the_key_go():
	target = message("")
	gesture, spoken = press(target, "control+rightArrow")
	assert gesture.sent == 1 and spoken == []


def test_reload_forgets_the_message():
	target = message("uma palavra")
	press(target, "control+rightArrow")
	overlays.reset_page_memory()
	assert overlays._Words.message is None
