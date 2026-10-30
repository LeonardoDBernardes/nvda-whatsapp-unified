"""Recuperacao de foco: contêiner -> linha lembrada; Esc legitimo nao recupera; sem laco."""

import core
import inputCore
import pytest
import speech
from controlTypes import State
from fakes import Page, focus

from globalPlugins.whatsAppUnified import GlobalPlugin, recovery

START = 1000.0


class Clock:
	def __init__(self):
		self.t = START

	def __call__(self):
		return self.t


@pytest.fixture
def clock(monkeypatch):
	c = Clock()
	monkeypatch.setattr(recovery, "now", c)
	return c


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


def deliver(plugin, obj):
	"""Um evento de foco passa pelo plugin global; devolve quantas vezes o NVDA 'falou' o objeto."""
	focus(obj)
	spoken_before = len(speech.spoken)
	calls = []

	def next_handler():
		calls.append(obj)
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)
	return calls, len(speech.spoken) - spoken_before


def fall_to_container(plugin, page, container=None):
	return deliver(plugin, container or page.chat_list)


def test_row_focus_is_remembered_and_spoken_normally(plugin, clock):
	page = Page().overlay_all()
	calls, spoken = deliver(plugin, page.chat_rows[1])
	assert calls == [page.chat_rows[1]] and spoken == 1
	assert recovery.remembered_row() is page.chat_rows[1]
	assert core.pending == []


def test_container_fall_is_silenced_then_recovers_to_the_remembered_row(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	speech.reset()
	clock.t += 5
	calls, spoken = fall_to_container(plugin, page)
	assert calls == [page.chat_list]  # o evento segue o caminho normal
	assert spoken == 0  # mas a fala do contêiner foi silenciada
	assert len(core.pending) == 1 and core.pending[0][0] == recovery.CHECK_DELAY_MS
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 1
	assert speech.spoken == []  # quem fala agora e o novo evento de foco da linha


def test_message_container_recovers_to_the_remembered_message(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.msg_rows[2])
	clock.t += 5
	fall_to_container(plugin, page, page.msg_list)
	core.run_pending()
	assert page.msg_rows[2].focus_calls == 1


def test_document_root_fall_recovers(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[0])
	clock.t += 5
	fall_to_container(plugin, page, page.doc)
	core.run_pending()
	assert page.chat_rows[0].focus_calls == 1


def test_wrong_kind_of_container_is_not_recovered(plugin, clock):
	"""Lembrei uma conversa; o foco caiu na lista de mensagens: o usuario foi para la de proposito."""
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[0])
	clock.t += 5
	calls, spoken = fall_to_container(plugin, page, page.msg_list)
	assert spoken == 1 and core.pending == []


@pytest.mark.parametrize("vk", sorted(recovery.LEGIT_KEYS))
def test_legit_keys_do_not_trigger_recovery(plugin, clock, vk):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	inputCore.decide_handleRawKey.decide(vkCode=vk, scanCode=0, extended=False, pressed=True)
	clock.t += 0.1
	calls, spoken = fall_to_container(plugin, page)
	assert spoken == 1  # fala normal, sem recuperar
	assert core.pending == []


def test_escape_old_enough_no_longer_counts_as_legit(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	inputCore.decide_handleRawKey.decide(vkCode=0x1B, scanCode=0, extended=False, pressed=True)
	clock.t += recovery.LEGIT_KEY_WINDOW_S + 0.5
	fall_to_container(plugin, page)
	assert len(core.pending) == 1


def test_key_handler_never_swallows_keys(plugin):
	assert inputCore.decide_handleRawKey.decide(vkCode=0x41, scanCode=0, extended=False, pressed=True)
	assert inputCore.decide_handleRawKey.decide(vkCode=0x1B, scanCode=0, extended=False, pressed=False)


def test_no_loop_at_most_one_recovery_per_second(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	fall_to_container(plugin, page)
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 1
	# O WhatsApp devolve o foco ao contêiner logo depois: nao recupera de novo na mesma hora.
	clock.t += 0.3
	calls, spoken = fall_to_container(plugin, page)
	assert spoken == 1 and core.pending == []
	assert page.chat_rows[1].focus_calls == 1
	# Passado o intervalo, pode recuperar outra vez.
	clock.t += 2
	fall_to_container(plugin, page)
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 2


def test_check_skips_when_focus_already_moved_on(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	fall_to_container(plugin, page)
	focus(page.composer)  # o usuario foi para o campo de digitacao
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 0


def test_check_inside_the_interval_speaks_the_container_instead_of_recovering(clock):
	page = Page().overlay_all()
	focus(page.chat_list)
	recovery._State.last_recovery_at = clock.t - 0.2
	recovery.check_focus(page.chat_list)
	assert speech.spoken and speech.spoken[0][1] is page.chat_list
	assert page.chat_rows[0].focus_calls == 0


def test_virtualized_row_falls_back_to_the_selected_row(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[2])
	page.chat_rows[2].states.add(State.DEFUNCT)  # a lista desmontou a linha
	page.chat_list.remove(page.chat_rows[2])
	clock.t += 5
	fall_to_container(plugin, page)
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 1  # a selecionada


def test_virtualized_message_row_falls_back_to_nearest_position(plugin, clock):
	page = Page().overlay_all()
	page.msg_rows[2].positionInfo = {"indexInGroup": 3}
	deliver(plugin, page.msg_rows[2])
	page.msg_rows[2].states.add(State.DEFUNCT)
	page.msg_list.remove(page.msg_rows[2])
	clock.t += 5
	fall_to_container(plugin, page, page.msg_list)
	core.run_pending()
	assert page.msg_rows[1].focus_calls == 1  # a linha mais proxima que sobrou


def test_nothing_to_recover_to_speaks_the_original_focus(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	for row in list(page.chat_rows):
		page.chat_list.remove(row)
	clock.t += 5
	fall_to_container(plugin, page)
	core.run_pending()
	assert speech.spoken and speech.spoken[-1][1] is page.chat_list


def test_option_off_disables_recovery(plugin, clock):
	import config
	from globalPlugins.whatsAppUnified import settings

	config.conf[settings.CONFIG_SECTION]["focusRecovery"] = False
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	calls, spoken = fall_to_container(plugin, page)
	assert spoken == 1 and core.pending == []


def test_other_site_is_never_touched(plugin, clock):
	other = Page(url="https://www.example.com/")
	calls, spoken = deliver(plugin, other.chat_list)
	assert calls == [other.chat_list] and spoken == 1 and core.pending == []


def test_event_is_delivered_exactly_once(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	calls, _spoken = fall_to_container(plugin, page)
	assert len(calls) == 1


def test_failure_in_recovery_still_delivers_the_event(plugin, clock, monkeypatch):
	page = Page().overlay_all()

	def boom(*args, **kwargs):
		raise RuntimeError("falha")

	monkeypatch.setattr(recovery, "handle_gain_focus", boom)
	calls, _spoken = deliver(plugin, page.chat_rows[0])
	assert len(calls) == 1


def test_terminate_unregisters_everything(clock):
	from speech.extensions import filter_speechSequence

	p = GlobalPlugin()
	assert filter_speechSequence.handlers and inputCore.decide_handleRawKey.handlers
	p.terminate()
	assert filter_speechSequence.handlers == [] and inputCore.decide_handleRawKey.handlers == []
