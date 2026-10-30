"""Exigencia do Leo: no WhatsApp Web o NVDA NAO toca o som de troca foco/navegacao.

O stub ``browseMode`` copia a logica do NVDA 2026.2: ``shouldPassThrough`` varia por objeto
e ``reportPassThrough`` toca o som quando o modo difere da variavel global ``.last``.
O teste de controle (classe nativa) prova que, sem o add-on, o som toca; os demais provam que
com a classe fixa ``WhatsAppChromeVBuf`` ele nunca toca e ``passThrough`` nunca muda.
"""

import browseMode
import config
import pytest
from controlTypes import Role, State
from fakes import Gesture, Node, Page, apply_overlays, focus
from NVDAObjects.IAccessible import chromium
from NVDAObjects.IAccessible.chromium import ChromeVBuf

from globalPlugins.whatsAppUnified import settings
from globalPlugins.whatsAppUnified.webmode import WhatsAppChromeVBuf, WhatsAppWebDocument


def focus_sequence(page):
	"""linha de conversa -> outra linha -> botao dentro da linha -> mensagem -> botao da mensagem
	-> campo de digitacao -> mensagem -> linha de conversa (a volta)."""
	return [
		page.chat_rows[0],
		page.chat_rows[1],
		page.chat_rows[1].firstChild.firstChild,  # botao dentro da celula
		page.msg_rows[0],
		page.msg_rows[0].lastChild,  # botao "Menu" da mensagem
		page.composer,
		page.msg_rows[1],
		page.chat_rows[0],
	]


def enter(ti, page, obj=None):
	"""O NVDA entra no documento: o foco ja esta em algum objeto dele."""
	focus(obj or page.chat_rows[0])
	ti.event_treeInterceptor_gainFocus()


def run_sequence(ti, page):
	delivered = []
	for obj in focus_sequence(page):
		focus(obj)
		ti.event_gainFocus(obj, lambda o=obj: delivered.append(o))
	return delivered


def test_control_native_buffer_flips_mode_and_plays_sound():
	"""CONTROLE: o buffer nativo do NVDA troca de modo e toca o som no mesmo percurso."""
	page = Page()
	ti = ChromeVBuf(page.doc)
	browseMode.reportPassThrough.last = False
	run_sequence(ti, page)
	assert ti.passThroughChanges, "o buffer nativo deveria trocar de modo neste percurso"
	assert len(browseMode.sounds) >= 2
	assert set(browseMode.sounds) == {"focusMode.wav", "browseMode.wav"}


def test_pinned_buffer_never_plays_sound_nor_changes_mode():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is True
	browseMode.reportPassThrough.last = False  # o Leo vinha de outra aba em modo de navegacao
	enter(ti, page)
	run_sequence(ti, page)
	assert browseMode.sounds == []
	assert ti.passThrough is True
	assert ti.passThroughChanges == []  # nem um unico set publico mudou o modo


def test_report_pass_through_returns_silently_for_every_focus_in_the_sequence():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	enter(ti, page)
	run_sequence(ti, page)
	assert browseMode.calls, "o NVDA chama reportPassThrough; o que importa e nao tocar"
	assert all(mode is True for mode, _only in browseMode.calls)
	assert browseMode.sounds == []


def test_should_pass_through_gives_the_same_answer_for_every_object():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	from controlTypes import OutputReason

	answers = {
		ti.shouldPassThrough(obj, OutputReason.FOCUS) for obj in focus_sequence(page)
	} | {ti.shouldPassThrough(obj, OutputReason.CARET) for obj in focus_sequence(page)}
	assert answers == {True}


def test_entering_the_document_is_silent_even_after_a_browse_mode_tab():
	page = Page()
	browseMode.reportPassThrough.last = False
	ti = WhatsAppChromeVBuf(page.doc)
	focus(page.chat_rows[0])
	ti.event_treeInterceptor_gainFocus()
	assert browseMode.sounds == []


def test_returning_to_whatsapp_after_another_document_stays_silent():
	"""Outra aba (modo de navegacao) muda o ``.last`` global; ao voltar nao toca."""
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	enter(ti, page)
	browseMode.reportPassThrough.last = False  # outra aba reportou "modo de navegacao"
	focus(page.msg_rows[0])
	ti.event_treeInterceptor_gainFocus()
	ti.event_gainFocus(page.msg_rows[0], lambda: None)
	assert browseMode.sounds == []


def test_escape_is_sent_to_the_page_and_keeps_focus_mode_silently():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	enter(ti, page)
	gesture = Gesture("escape")
	ti.script_disablePassThrough(gesture)
	assert gesture.sent == 1
	assert ti.passThrough is True
	assert browseMode.sounds == []


def test_nvda_space_is_native_and_plays_the_sound_only_on_purpose():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	enter(ti, page)
	focus(page.msg_rows[0])
	browseMode.toggle_pass_through(ti)  # NVDA+Espaco: sai do modo foco
	assert ti.passThrough is False
	assert ti.disableAutoPassThrough is False
	assert browseMode.sounds == ["browseMode.wav"]
	# Escolha do Leo respeitada: em modo de navegacao, linhas e botoes NAO puxam o modo foco.
	for obj in (page.chat_rows[0], page.msg_rows[0], page.msg_rows[0].lastChild):
		ti.event_gainFocus(obj, lambda: None)
		assert ti.passThrough is False
	assert browseMode.sounds == ["browseMode.wav"]
	browseMode.toggle_pass_through(ti)  # NVDA+Espaco de novo: volta ao modo foco fixo
	assert ti.passThrough is True
	assert ti.disableAutoPassThrough is True
	assert browseMode.sounds == ["browseMode.wav", "focusMode.wav"]
	run_sequence(ti, page)
	assert browseMode.sounds == ["browseMode.wav", "focusMode.wav"]


def test_browse_mode_choice_still_enters_text_fields_like_nvda():
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	enter(ti, page)
	browseMode.toggle_pass_through(ti)  # o Leo escolheu navegacao
	ti.event_gainFocus(page.composer, lambda: None)
	assert ti.passThrough is True  # regra nativa de campo editavel


def test_other_site_keeps_the_native_buffer():
	page = Page(url="https://www.example.com/")
	doc = page.doc
	apply_overlays(doc, {"web"})
	assert not isinstance(doc, WhatsAppWebDocument)
	assert doc.treeInterceptorClass is ChromeVBuf


def test_other_site_buffer_is_not_pinned_and_behaves_natively():
	page = Page(url="https://www.example.com/")
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is False
	assert ti.disableAutoPassThrough is False
	browseMode.reportPassThrough.last = False
	ti.event_gainFocus(page.composer, lambda: None)
	assert ti.passThrough is True  # nativo
	ti.event_gainFocus(page.msg_rows[0], lambda: None)
	assert ti.passThrough is False  # nativo (e toca o som, como sempre)
	assert "browseMode.wav" in browseMode.sounds


def test_whatsapp_document_gets_the_pinned_buffer_class():
	page = Page()
	doc = page.doc
	apply_overlays(doc, {"web"})
	assert isinstance(doc, WhatsAppWebDocument)
	assert doc.treeInterceptorClass is WhatsAppChromeVBuf


def test_scope_desktop_only_leaves_the_web_document_alone():
	config.conf[settings.CONFIG_SECTION]["scope"] = "desktop"
	page = Page()
	doc = page.doc
	apply_overlays(doc, {"web"})
	assert not isinstance(doc, WhatsAppWebDocument)
	assert doc.treeInterceptorClass is ChromeVBuf


def test_option_off_gives_native_behavior():
	config.conf[settings.CONFIG_SECTION]["autoFocusMode"] = False
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is False
	ti.event_gainFocus(page.composer, lambda: None)
	ti.event_gainFocus(page.msg_rows[0], lambda: None)
	assert ti.passThroughChanges == [True, False]


def test_old_disable_focus_lock_switch_is_honored():
	config.conf[settings.CONFIG_SECTION]["disableFocusLock"] = True
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is False


def test_document_without_url_uses_window_title_and_pins_silently():
	page = Page(url=None, title="(1) WhatsApp - Google Chrome")
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is True
	browseMode.reportPassThrough.last = False
	enter(ti, page)
	run_sequence(ti, page)
	assert browseMode.sounds == []


def test_url_arriving_after_creation_pins_without_sound():
	"""about:blank no nascimento; o endereco do WhatsApp chega depois."""
	page = Page(url="about:blank", title="Nova guia - Google Chrome")
	ti = WhatsAppChromeVBuf(page.doc)
	assert ti.passThrough is False
	page.doc.IAccessibleObject.url = "https://web.whatsapp.com/"
	browseMode.reportPassThrough.last = False
	ti.event_gainFocus(page.chat_rows[0], lambda: None)
	assert ti.passThrough is True
	assert browseMode.sounds == []


def test_event_gain_focus_is_delivered_even_while_loading():
	assert getattr(WhatsAppChromeVBuf.event_gainFocus, "ignoreIsReady", False) is True


def test_other_buffer_after_whatsapp_keeps_native_sounds():
	"""Sair do WhatsApp para um documento nativo: o som nativo continua valendo ali."""
	whats = Page()
	other = Page(url="https://www.example.com/")
	wa_ti = WhatsAppChromeVBuf(whats.doc)
	enter(wa_ti, whats)
	other_ti = ChromeVBuf(other.doc)
	other_ti.event_gainFocus(other.msg_rows[0], lambda: None)
	other_ti.event_gainFocus(other.composer, lambda: None)
	assert "focusMode.wav" in browseMode.sounds


def test_chromium_document_stub_is_a_real_subclass():
	assert issubclass(WhatsAppWebDocument, chromium.Document)


@pytest.mark.parametrize("role", [Role.BUTTON, Role.TABLEROW, Role.TABLECELL, Role.EDITABLETEXT, Role.LINK if hasattr(Role, "LINK") else Role.PANE])
def test_pinned_answer_ignores_role(role):
	page = Page()
	ti = WhatsAppChromeVBuf(page.doc)
	from controlTypes import OutputReason

	node = Node(role, "x", states={State.FOCUSABLE})
	assert ti.shouldPassThrough(node, OutputReason.FOCUS) is True
