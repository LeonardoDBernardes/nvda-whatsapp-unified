"""Diagnostico no log do NVDA (INFO): toda acao do add-on deixa rastro, com limites e sem conteudo."""

import config
import core
import logHandler
import pytest
from fakes import Gesture, Page, apply_overlays, focus

from globalPlugins.whatsAppUnified import GlobalPlugin, diag, filters, recovery, settings
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf

SEGREDO = "SEGREDO-DA-MENSAGEM-12345"


def lines():
	return [line for line in logHandler.log.lines if line.startswith(diag.PREFIX)]


class Clock:
	t = 100.0


@pytest.fixture
def tick(monkeypatch):
	"""Relogio da diagnostico controlado pelo teste."""
	clock = Clock()
	clock.t = 100.0
	monkeypatch.setattr(diag.time, "monotonic", lambda: clock.t)
	return clock


@pytest.fixture
def plugin():
	p = GlobalPlugin()
	yield p
	p.terminate()


# ─── limites ─────────────────────────────────────────────────────────────────

def test_prefix_and_one_line_per_action_every_two_seconds(tick):
	diag.act("overlay", "a")
	diag.act("overlay", "b")  # mesma acao, menos de 2 s depois
	assert lines() == ["WhatsAppUnificado: overlay a"]
	tick.t += 1.9
	diag.act("overlay", "c")
	assert len(lines()) == 1
	tick.t += 0.2
	diag.act("overlay", "d")
	assert lines()[-1] == "WhatsAppUnificado: overlay d" and len(lines()) == 2
	diag.act("script", "x")  # outra acao: nao depende da anterior
	assert len(lines()) == 3


def test_at_most_200_lines_per_session_and_a_single_stop_notice(tick):
	for index in range(260):
		tick.t += 3
		diag.act("overlay", str(index))
	written = lines()
	assert len(written) == 201
	assert "limite de 200 linhas" in written[-1]
	assert diag.lines_written() == 200


def test_option_off_writes_nothing(tick):
	config.conf[settings.CONFIG_SECTION]["diagLog"] = False
	diag.act("overlay", "a")
	assert lines() == []
	config.conf[settings.CONFIG_SECTION]["diagLog"] = True
	diag.act("overlay", "a")
	assert len(lines()) == 1


def test_option_is_on_by_default_and_in_the_panel_spec():
	assert settings.DEFAULTS["diagLog"] is True
	assert "diagLog" in settings.SPEC
	assert settings.get("diagLog") is True


def test_diag_never_raises(monkeypatch):
	monkeypatch.setattr(diag.log, "info", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("log quebrado")))
	diag.act("overlay", "a")  # nao pode propagar


# ─── cada acao deixa rastro ──────────────────────────────────────────────────

def test_overlay_is_logged_with_class_app_and_role_only(plugin, tick):
	page = Page()
	focus(page.composer)
	apply_overlays(page.msg_rows[0], {"web"})
	assert any("overlay classe=MessageRow app=chrome papel=TABLEROW" in line for line in lines()), lines()


def test_context_transitions_are_logged(plugin, tick):
	page = Page()
	api_focus(plugin, page.composer)
	assert any("contexto WhatsApp Web confirmado" in line for line in lines())
	other = Page(url="https://www.example.com/")
	tick.t += 5
	api_focus(plugin, other.composer)
	assert any("contexto saiu do WhatsApp Web" in line for line in lines())


def api_focus(plugin, obj):
	import api

	api.setFocusObject(obj)
	plugin.event_gainFocus(obj, lambda: None)


def test_focus_deferral_and_recovery_are_logged(plugin, tick, monkeypatch):
	page = Page().overlay_all()
	clock = Clock()
	monkeypatch.setattr(recovery, "now", lambda: clock.t)
	api_focus(plugin, page.chat_rows[1])
	clock.t += 5
	tick.t += 5
	api_focus(plugin, page.chat_list)
	assert any("foco-adiado" in line for line in lines()), lines()
	tick.t += 5
	core.run_pending()
	assert any("foco-recuperado tipo=chat" in line for line in lines()), lines()


def test_script_execution_is_logged_by_name(plugin, tick):
	page = Page().overlay_all()
	focus(page.composer)
	plugin.script_togglePhoneFilter(Gesture("control+shift+e"))
	assert any(line.endswith("script togglePhoneFilter") for line in lines()), lines()
	row = page.msg_rows[0]
	focus(row)
	row.script_copyMessage(Gesture("control+c"))
	assert any(line.endswith("script copyMessage") for line in lines()), lines()


def test_filtered_speech_is_logged_with_sizes_never_text(plugin, tick):
	page = Page()
	row = page.chat_rows[0]
	row.name = "Talvez %s" % SEGREDO
	focus(page.composer)
	apply_overlays(row, {"web"})
	focus(row)
	result = filters.on_speech_sequence([row.name, "extra"])
	assert result[0] == SEGREDO
	mine = [line for line in lines() if "fala-filtrada" in line]
	assert mine and "tipo=chat" in mine[0]
	assert SEGREDO not in mine[0] and "Talvez" not in mine[0]


def test_pin_and_release_of_focus_mode_are_logged(plugin, tick):
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	page.attach(ti)
	focus(page.composer)
	ti.event_treeInterceptor_gainFocus()
	assert any("modo-foco-fixado" in line for line in lines()), lines()
	tick.t += 5
	config.conf[settings.CONFIG_SECTION]["autoFocusMode"] = False
	ti.event_gainFocus(page.composer, lambda: None)
	assert any("modo-foco-solto motivo=opcao" in line for line in lines()), lines()


def test_nothing_is_ever_logged_with_message_content(plugin, tick):
	page = Page()
	secret_row = page.msg_rows[0]
	secret_row.name = "Fulano: %s" % SEGREDO
	# nome, valor e filhos com o texto secreto
	secret_row.value = SEGREDO
	secret_row.firstChild.name = SEGREDO
	api_focus(plugin, page.composer)
	for step in range(5):
		tick.t += 3
		apply_overlays(secret_row, {"web"})
		api_focus(plugin, secret_row)
		filters.on_speech_sequence([secret_row.name])
		secret_row.script_copyMessage(Gesture("control+c"))
		secret_row.script_readFull(Gesture("control+r"))
	assert lines(), "esperava rastro de diagnostico"
	assert not any(SEGREDO in line for line in logHandler.log.lines)
