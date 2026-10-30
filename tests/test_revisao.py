"""Pontos da revisao independente da 2.0.0: configuracao, desempenho, recarga, mouse, memoria da pagina."""

import os
import sys
import time

import api
import config
import core
import mouseHandler
import pytest
import speech
import winUser
from controlTypes import Role, State
from fakes import Gesture, Node, Page, focus

import NVDAObjects.IAccessible as iaccessible
from globalPlugins.whatsAppUnified import GlobalPlugin, context, overlays, recovery, settings, tree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ─── 1. configuracao: booleanos que voltam como TEXTO do ConfigObj ───────────

def conf_as_configobj(**values):
	"""Imita o ConfigObj: chaves SEM especificacao voltam como texto ('True' / 'False')."""
	section = config.conf[settings.CONFIG_SECTION]
	section.clear()
	section.update(values)
	return section


@pytest.mark.parametrize(
	"text,expected",
	[("True", True), ("true", True), ("1", True), ("yes", True), ("on", True), (" True ", True),
	 ("False", False), ("false", False), ("0", False), ("no", False), ("off", False), ("", False)],
)
def test_as_bool_reads_text_values(text, expected):
	assert settings.as_bool(text) is expected


def test_old_key_saved_as_text_false_does_not_turn_the_auto_focus_mode_off():
	conf_as_configobj(disableFocusLock="False")  # quem salvou o painel da 1.4.x
	assert settings.get("autoFocusMode") is True


def test_old_key_saved_as_text_true_still_turns_it_off():
	conf_as_configobj(disableFocusLock="True")
	assert settings.get("autoFocusMode") is False


def test_every_boolean_option_is_parsed_from_text():
	conf_as_configobj(
		filterMessageList="False", filterChatList="True", filterUsageHints="False",
		filterTalvez="False", autoFocusMode="False", focusRecovery="False",
	)
	assert settings.get("filterMessageList") is False
	assert settings.get("filterChatList") is True
	assert settings.get("filterUsageHints") is False
	assert settings.get("filterTalvez") is False
	assert settings.get("autoFocusMode") is False
	assert settings.get("focusRecovery") is False
	assert settings.get("scope") == "both"  # texto de verdade continua texto


def test_missing_options_use_the_defaults():
	conf_as_configobj()
	for key, default in settings.DEFAULTS.items():
		assert settings.get(key) == default


def test_toggling_a_filter_starting_from_text_values():
	conf_as_configobj(filterMessageList="False")
	plugin = GlobalPlugin()
	plugin.script_togglePhoneFilter(Gesture("control+shift+e"))
	assert settings.get("filterMessageList") is True


def test_saving_the_panel_deletes_the_old_key_instead_of_rewriting_it():
	class Box:
		def __init__(self, checked):
			self.checked = checked

		def IsChecked(self):
			return self.checked

		def GetSelection(self):
			return 2

	section = conf_as_configobj(disableFocusLock="True", autoFocusMode="False")
	panel = type("FakePanel", (), {})()
	for name in ("filterMessageList", "filterChatList", "filterUsageHints", "filterTalvez", "autoFocusMode", "focusRecovery"):
		setattr(panel, name, Box(True))
	panel.scope = Box(True)
	settings.WhatsAppUnifiedSettings.onSave(panel)
	assert "disableFocusLock" not in section  # apagada, nao regravada
	assert section["autoFocusMode"] is True
	assert settings.get("autoFocusMode") is True
	assert all(isinstance(section[key], bool) for key in settings.DEFAULTS if key != "scope")


# ─── 3. desempenho: prazos, sem varreduras, sem caminhar na decisao da tecla ─

def test_walk_honors_an_expired_deadline():
	page = Page()
	seen = []
	assert tree.walk(page.doc, lambda o: seen.append(o) and False, deadline=time.monotonic() - 1) is None
	assert seen == []


class SlowNode(Node):
	"""Cada leitura de filhos custa 20 ms (um COM lento)."""

	@property
	def firstChild(self):
		time.sleep(0.02)
		return super().firstChild


def slow_page(count=120):
	page = Page()
	page.main.remove(page.composer)
	page.main.remove(page.call_button)
	for index in range(count):
		page.main.add(SlowNode(Role.SECTION, "n%d" % index))
	return page


@pytest.mark.parametrize("command", ["script_focusComposer", "script_goToMessageList", "script_goToChatList", "script_openCallMenu"])
def test_each_navigation_command_stays_inside_the_command_time(command):
	plugin = GlobalPlugin()
	page = slow_page()
	page.chat_list.name = "outra coisa"  # nao ha lista de conversas nem campo: busca ate o prazo
	focus(page.main)
	start = time.monotonic()
	getattr(plugin, command)(Gesture("alt+d"))
	elapsed = time.monotonic() - start
	assert elapsed < 0.6, elapsed  # prazo do comando ~0,3 s (+ folga de um passo lento)


def test_find_message_list_divides_one_deadline_among_its_steps():
	page = slow_page()
	start = time.monotonic()
	tree.find_message_list(page.doc, deadline=tree.new_deadline(0.2))
	assert time.monotonic() - start < 0.5


def test_player_search_shares_one_deadline(monkeypatch):
	from globalPlugins.whatsAppUnified import messagetext

	seconds = []
	original = tree.walk

	def spy(root, predicate, **kwargs):
		seconds.append(kwargs.get("deadline"))
		return original(root, predicate, **kwargs)

	monkeypatch.setattr(messagetext, "walk", spy)
	row = Page().msg_rows[0]
	messagetext.play_target(row)
	assert len(seconds) >= 2 and len(set(seconds)) == 1 and seconds[0] is not None


def test_text_collection_has_a_time_limit():
	from globalPlugins.whatsAppUnified import messagetext

	row = Node(Role.TABLEROW, "")
	for index in range(100):
		row.add(SlowNode(Role.STATICTEXT, "texto %d" % index))
	start = time.monotonic()
	messagetext.collect_texts(row)
	assert time.monotonic() - start < 0.5


def test_document_root_does_not_use_the_foreground_window_in_the_browser(monkeypatch):
	orphan = Node(Role.EDITABLETEXT, "x")
	api.setFocusObject(orphan, ancestors=[])
	monkeypatch.setattr(api, "getForegroundObject", lambda: pytest.fail("varreu a janela inteira"))
	assert tree.document_root(orphan) is None
	monkeypatch.undo()
	api.setForegroundObject(orphan)
	assert tree.document_root(orphan, allow_foreground=True) is orphan


def test_commands_in_the_browser_without_a_document_just_say_not_found(monkeypatch):
	import ui

	page = Page()
	api.setFocusObject(page.composer, ancestors=[])  # cadeia sem DOCUMENT
	monkeypatch.setattr(api, "getForegroundObject", lambda: pytest.fail("varreu a janela inteira"))
	plugin = GlobalPlugin()
	plugin.script_focusComposer(Gesture("alt+d"))
	assert ui.messages[-1] == "Campo de digitação não encontrado"


def test_row_classification_is_cached_per_container(monkeypatch):
	page = Page()
	calls = []
	original = context.find_composer
	monkeypatch.setattr(context, "find_composer", lambda *a, **k: calls.append(1) or original(*a, **k))
	for row in page.msg_rows * 3:
		assert context.row_kind(row) == "message"
	assert len(calls) == 1  # a busca do campo de digitacao roda uma vez para a lista toda


def test_message_classification_search_is_bounded():
	page = Page()
	page.main.remove(page.composer)
	for index in range(200):
		page.main.add(SlowNode(Role.SECTION, "n%d" % index))
	context.forget_kinds()
	start = time.monotonic()
	assert context.row_kind(page.msg_rows[0]) is None
	assert time.monotonic() - start < 0.5


def test_unconfirmed_web_page_creates_no_overlay_and_makes_no_walk(monkeypatch):
	from fakes import apply_overlays

	page = Page(url=None, title="WhatsApp - Google Chrome")
	monkeypatch.setattr(tree, "walk", lambda *a, **k: pytest.fail("varredura sem endereco confirmado"))
	assert apply_overlays(page.msg_rows[0], {"web"}) == []
	assert apply_overlays(page.chat_rows[0], {"web"}) == []


# ─── 8. recarga (NVDA+Ctrl+F3) ───────────────────────────────────────────────

def test_app_module_imports_the_package_at_call_time_not_at_load():
	sys.path.insert(0, ROOT)
	try:
		import appModules.whatsapp_root as module
	finally:
		sys.path.remove(ROOT)
	assert not hasattr(module, "overlays")
	calls = []

	class FakeOverlays:
		@staticmethod
		def choose_overlay_classes(obj, clsList, contexts):
			calls.append(("novo", contexts))

	original = sys.modules["globalPlugins.whatsAppUnified.overlays"]
	sys.modules["globalPlugins.whatsAppUnified.overlays"] = FakeOverlays
	import globalPlugins.whatsAppUnified as package

	package_overlays = package.overlays
	package.overlays = FakeOverlays  # o "from pacote import overlays" olha o atributo do pacote
	try:
		module.AppModule().chooseNVDAObjectOverlayClasses(Node(Role.TABLEROW, "x"), [])
	finally:
		sys.modules["globalPlugins.whatsAppUnified.overlays"] = original
		package.overlays = package_overlays
	assert calls == [("novo", {"app"})]  # usou a copia atual, nao uma guardada no topo


def test_terminate_drops_references_and_verdicts():
	plugin = GlobalPlugin()
	page = Page()
	overlays.note_page_focus(page.composer)
	context.raw_context(page.composer)
	context.row_kind(page.msg_rows[0])
	assert overlays._PageMemory.last is page.composer
	plugin.terminate()
	assert overlays._PageMemory.last is None and overlays._PageMemory.hwnd == 0
	assert context._hwnd_cache == {} and context._kind_cache == {}
	assert recovery._State.row_ref is None


# ─── 9. painel-hospedeiro: objeto morto ──────────────────────────────────────

def test_host_pane_ignores_a_dead_remembered_object():
	page = Page()
	overlays.note_page_focus(page.composer)
	page.composer.states.add(State.DEFUNCT)
	assert overlays.real_page_focus() is None
	pane = overlays.HostPane.__new__(overlays.HostPane)
	assert pane._get_focusRedirect() is None
	assert overlays._PageMemory.last is None  # soltou a referencia morta


def test_host_pane_ignores_a_dead_active_child_and_com_errors():
	page = Page()
	overlays.note_page_focus(page.composer)

	class Document(Node):
		def __init__(self, active):
			super().__init__(Role.DOCUMENT, "doc")
			self._active = active

		@property
		def activeChild(self):
			if isinstance(self._active, Exception):
				raise self._active
			return self._active

	dead = Node(Role.EDITABLETEXT, "morto", states={State.DEFUNCT})
	key = (page.composer.windowHandle, winUser.OBJID_CLIENT, 0)
	iaccessible.events[key] = Document(dead)
	try:
		assert overlays.real_page_focus() is page.composer  # o ativo esta morto: usa o ultimo vivo
		iaccessible.events[key] = Document(OSError("COM"))
		assert overlays.real_page_focus() is page.composer
		alive = Node(Role.EDITABLETEXT, "vivo")
		iaccessible.events[key] = Document(alive)
		assert overlays.real_page_focus() is alive
	finally:
		iaccessible.events.clear()


def test_host_pane_never_raises_on_com_failure(monkeypatch):
	monkeypatch.setattr(overlays, "real_page_focus", lambda: (_ for _ in ()).throw(OSError("COM")))
	pane = overlays.HostPane.__new__(overlays.HostPane)
	assert pane._get_focusRedirect() is None


# ─── 11. clique de mouse e movimento legitimo ────────────────────────────────

class Clock:
	def __init__(self):
		self.t = 1000.0

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
	focus(obj)
	before = len(speech.spoken)

	def next_handler():
		obj.reportFocus()

	plugin.event_gainFocus(obj, next_handler)
	return len(speech.spoken) - before


def test_recent_mouse_event_is_a_legit_focus_move_and_not_recovered(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	mouseHandler.lastMouseEventTime = time.time()  # clique ha instantes
	spoken = deliver(plugin, page.chat_list)
	assert spoken == 1 and core.pending == []


def test_pressed_mouse_button_is_a_legit_focus_move(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	winUser._buttons_down.add(winUser.VK_LBUTTON)
	spoken = deliver(plugin, page.chat_list)
	assert spoken == 1 and core.pending == []


def test_old_mouse_event_does_not_block_the_recovery(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	mouseHandler.lastMouseEventTime = time.time() - 30
	deliver(plugin, page.chat_list)
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 1


def test_click_between_the_event_and_the_check_cancels_the_recovery(plugin, clock):
	page = Page().overlay_all()
	deliver(plugin, page.chat_rows[1])
	clock.t += 5
	deliver(plugin, page.chat_list)
	assert len(core.pending) == 1
	mouseHandler.lastMouseEventTime = time.time()
	core.run_pending()
	assert page.chat_rows[1].focus_calls == 0
	assert any(entry[0] == "object" or entry for entry in speech.spoken)  # falou o foco original


# ─── 12. manifest ────────────────────────────────────────────────────────────

def test_manifest_versions():
	with open(os.path.join(ROOT, "manifest.ini"), encoding="utf-8") as handle:
		text = handle.read()
	assert "version = 2.0.0" in text
	assert "minimumNVDAVersion = 2026.1" in text
	assert "lastTestedNVDAVersion = 2026.2" in text
