# -*- coding: UTF-8 -*-
"""Recuperar o foco quando o WhatsApp o perde.

POR QUE EXISTE (código da página, build de 29/10/2026): a lista de conversas e a
de mensagens são virtualizadas. Quando a linha com foco é desmontada, o foco cai
no contêiner da lista, no corpo da página ou no documento. O WhatsApp também
devolve o foco ao contêiner quando ele sai da lista, e depois de Alt+Tab as
mensagens perdem o nome. Para quem usa leitor de tela isso é "caí no nada".

COMO FUNCIONA:
1. Lembra a última linha (conversa ou mensagem) que recebeu foco: o objeto, o
   tipo da lista, o nome e a posição.
2. Quando o foco cai na raiz do documento, no painel-corpo ou num contêiner de
   lista do mesmo tipo da linha lembrada, e nenhuma tecla que legitimamente tira
   o foco foi apertada há pouco (Esc, Tab, Enter, F6, Windows), NÃO fala o
   contêiner na hora: entrega o evento em silêncio e agenda uma conferência
   (``core.callLater``, 200 ms).
3. Se o foco ainda está lá: devolve o foco à linha lembrada (se ainda existe com
   o mesmo nome), senão à linha SELECIONADA da mesma lista, senão à linha mais
   próxima pela posição, senão à primeira. O novo evento de foco fala a linha
   normalmente. Se não achar nada, fala o foco original.
4. No máximo uma recuperação por segundo: nunca entra em laço.
"""

import time

import api
import core
import inputCore
import mouseHandler
import speech
import winUser
from controlTypes import OutputReason

from . import diag, settings
from .context import active, raw_context, wa_context
from .tree import (
	LIST_ROLES,
	Role,
	State,
	find_chat_list,
	find_message_list,
	is_chat_list_container,
	ancestors,
	is_defunct,
	document_root,
	focusable_in,
	new_deadline,
	row_ancestor,
	rows_of,
	safe_name,
	safe_role,
	safe_states,
	selected_or_first,
)

CHECK_DELAY_MS = 200
MIN_INTERVAL_S = 1.0  # no máximo uma recuperação por segundo
LEGIT_KEY_WINDOW_S = 0.6  # tecla que tira o foco de propósito, de pouco antes
REMEMBER_FRESH_S = 2.0  # "a linha foi o foco há pouco"
MOUSE_WINDOW_S = 0.6  # clique ou movimento de mouse de pouco antes também é intencional

# Teclas virtuais que movem o foco de propósito (Esc, Tab, Enter, F6, Windows,
# Espaço, tecla de aplicativos e F10). Espaço e tecla de aplicativos abrem o menu
# da mensagem (relato do Leo, 30/10/2026: na 2.0.1 o Espaço deixou de abrir o
# menu no aplicativo; sem elas aqui a recuperação podia puxar o foco de volta
# para a mensagem enquanto o menu abria).
LEGIT_KEYS = frozenset((0x1B, 0x09, 0x0D, 0x75, 0x5B, 0x5C, 0x20, 0x5D, 0x79))


class _State:
	row_ref = None  # última linha com foco (referência forte, ver remember)
	kind = None  # 'chat' | 'message'
	name = ""
	index = 0
	seen_at = 0.0
	last_key = 0
	last_key_at = 0.0
	last_recovery_at = 0.0


def reset():
	_State.row_ref = None
	_State.kind = None
	_State.name = ""
	_State.index = 0
	_State.seen_at = 0.0
	_State.last_key = 0
	_State.last_key_at = 0.0
	_State.last_recovery_at = 0.0


def now():
	return time.monotonic()


# ─── teclas ──────────────────────────────────────────────────────────────────

def on_raw_key(vkCode=0, scanCode=0, extended=False, pressed=True, **kwargs):
	"""Handler de ``inputCore.decide_handleRawKey``: só anota a tecla e deixa passar.

	Fora do WhatsApp nem anota: sai na primeira linha.
	"""
	if active() is None:
		return True
	if pressed:
		_State.last_key = vkCode
		_State.last_key_at = now()
	return True


def legit_key_recent(at=None):
	at = now() if at is None else at
	return _State.last_key in LEGIT_KEYS and (at - _State.last_key_at) <= LEGIT_KEY_WINDOW_S


def mouse_recent(at=None):
	"""Houve clique de mouse agora ou evento de mouse há pouco? (movimento legítimo de foco)

	Um clique pode mover o foco para um contêiner de propósito; recuperar a
	linha lembrada brigaria com o usuário. O NVDA anota o instante do último
	evento de mouse; o estado dos botões cobre o clique ainda apertado.
	"""
	try:
		for button in (winUser.VK_LBUTTON, winUser.VK_RBUTTON, winUser.VK_MBUTTON):
			if winUser.getAsyncKeyState(button) & 0x8000:
				return True
	except Exception:
		pass
	try:
		return (time.time() - mouseHandler.lastMouseEventTime) <= MOUSE_WINDOW_S
	except Exception:
		return False


def register_keys():
	inputCore.decide_handleRawKey.register(on_raw_key)


def unregister_keys():
	try:
		inputCore.decide_handleRawKey.unregister(on_raw_key)
	except Exception:
		pass


# ─── lembrar a linha ─────────────────────────────────────────────────────────

def _index_of(obj):
	try:
		info = obj.positionInfo
		return max(int(info.get("indexInGroup", 1)) - 1, 0)
	except Exception:
		return 0


def remember(obj):
	"""Chamado a cada foco numa linha do WhatsApp."""
	kind = getattr(obj, "wa_kind", None)
	if kind not in ("chat", "message"):
		return
	# Referência forte de propósito: o NVDA descarta o objeto assim que o foco
	# sai dele, então uma referência fraca morreria na hora. É um ponteiro só; se
	# a linha foi desmontada pela virtualização, ``is_defunct`` percebe.
	_State.row_ref = obj
	_State.kind = kind
	_State.name = safe_name(obj)
	# O foco fica no div de dentro da linha; a posição é a da linha.
	row = obj if safe_role(obj) == Role.TABLEROW else row_ancestor(obj)
	_State.index = _index_of(row if row is not None else obj)
	_State.seen_at = now()


def remembered_row():
	return _State.row_ref


# ─── onde o foco caiu? ───────────────────────────────────────────────────────

def landing_kind(obj):
	"""'root' (documento/painel-corpo), 'chat' / 'message' (contêiner de lista) ou None."""
	role = safe_role(obj)
	if role == Role.DOCUMENT:
		return "root"
	if role == Role.PANE and not safe_name(obj):
		return "root"
	if role in LIST_ROLES:
		if is_chat_list_container(obj):
			return "chat"
		# Lista de mensagens: contêiner sem nome cujas filhas são linhas.
		if not safe_name(obj) and _first_child_is_row(obj):
			return "message"
	return None


def _first_child_is_row(obj):
	try:
		child = obj.firstChild
	except Exception:
		return False
	return child is not None and safe_role(child) == Role.TABLEROW


def should_defer(obj, at=None):
	"""Esta queda de foco é candidata a recuperação? (Não agenda nada.)"""
	if not settings.get("focusRecovery"):
		return False
	at = now() if at is None else at
	if _State.row_ref is None or _State.kind is None:
		return False
	if at - _State.last_recovery_at < MIN_INTERVAL_S:
		return False
	if legit_key_recent(at) or mouse_recent():
		return False
	kind = landing_kind(obj)
	if kind is None:
		return False
	if kind == "root":
		return True
	return kind == _State.kind


# ─── escolher a linha de destino ─────────────────────────────────────────────

def _alive_same_name(row):
	if row is None or is_defunct(row):
		return False
	return safe_name(row) == _State.name or not _State.name


def _list_container_for(obj, kind):
	"""O contêiner da lista do tipo ``kind`` (a partir do objeto onde o foco caiu)."""
	if landing_kind(obj) == kind:
		return obj
	if safe_role(obj) == Role.DOCUMENT:
		root = obj
	else:
		# Só o aplicativo aceita a janela inteira como reserva; no navegador
		# isso seria varrer o Chrome todo.
		root = document_root(obj, allow_foreground=raw_context(obj) == "app")
	deadline = new_deadline()
	if kind == "chat":
		return find_chat_list(root, deadline)
	return find_message_list(root, deadline)


def pick_target(obj):
	"""Linha que deve receber o foco, ou None."""
	kind = _State.kind
	container = _list_container_for(obj, kind)
	if container is None:
		return None
	remembered = remembered_row()
	if _alive_same_name(remembered):
		if any(parent == container for parent in ancestors(remembered, 7)):
			return remembered
	rows = rows_of(container)
	if not rows:
		return None
	row = None
	for candidate in rows:
		if State.SELECTED in safe_states(candidate):
			row = candidate
			break
	if row is None:
		if kind == "chat":
			row = selected_or_first(rows)
		else:
			row = rows[min(_State.index, len(rows) - 1)]
	# A linha de mensagem não aceita foco: o foco vai para o div focável dela.
	return focusable_in(row) or row


# ─── tratar o evento de foco ─────────────────────────────────────────────────

def _silent_report():
	"""Substitui ``reportFocus`` do objeto enquanto a queda de foco é conferida."""


def handle_gain_focus(obj, nextHandler):
	"""Chamado pelo plugin global em todo evento de foco do WhatsApp.

	Devolve True se tratou o evento (não chame ``nextHandler`` de novo).
	"""
	if wa_context() is None:
		return False
	remember(obj)
	if not should_defer(obj):
		return False
	diag.act("foco-adiado", "tipo=%s %s" % (_State.kind, diag.describe(obj)))
	obj.reportFocus = _silent_report
	try:
		nextHandler()
	finally:
		try:
			del obj.reportFocus
		except Exception:
			pass
	core.callLater(CHECK_DELAY_MS, check_focus, obj)
	return True


def check_focus(obj):
	"""Conferência agendada: ainda está no contêiner? Então recupera ou fala o foco."""
	try:
		if api.getFocusObject() != obj:
			return  # o foco já foi para outro lugar e falou sozinho
		at = now()
		if at - _State.last_recovery_at < MIN_INTERVAL_S or mouse_recent():
			diag.act("foco-falado-original", "motivo=intervalo-ou-mouse")
			speech.speakObject(obj, reason=OutputReason.FOCUS)
			return
		target = pick_target(obj)
		if target is None:
			diag.act("foco-falado-original", "motivo=sem-alvo")
			speech.speakObject(obj, reason=OutputReason.FOCUS)
			return
		_State.last_recovery_at = at
		diag.act("foco-recuperado", "tipo=%s %s" % (_State.kind, diag.describe(target)))
		target.setFocus()
	except Exception:
		try:
			speech.speakObject(obj, reason=OutputReason.FOCUS)
		except Exception:
			pass
