# -*- coding: UTF-8 -*-
"""Percorrer a árvore de objetos do NVDA com segurança e achar partes do WhatsApp.

Tudo aqui anda pelos NVDAObjects a partir da raiz do documento do WhatsApp e
NUNCA exige um tree interceptor: no aplicativo o NVDA desliga o modo de
navegação (disableBrowseModeByDefault), então ``focus.treeInterceptor`` é None.

As partes são achadas só por papel + nome acessível + estrutura. Nunca por
nome de classe CSS ou posição fixa: o WhatsApp muda isso no servidor.
"""

import re
import time

import api
import controlTypes

Role = controlTypes.Role
State = controlTypes.State

# Nome acessível da lista de conversas (e da lista durante uma pesquisa).
CHAT_LIST_RE = re.compile(
	r"(lista de conversas|lista de chats?|chat list|chats? list|liste des discussions|"
	r"liste de discussions|chatliste|elenco chat|elenco delle chat|"
	r"resultados da pesquisa|search results|resultados de b[uú]squeda|"
	r"r[eé]sultats de (la )?recherche|suchergebnisse)",
	re.IGNORECASE,
)

# Nome do campo de digitação, usado só quando o estado MULTILINE não vier.
COMPOSER_NAME_RE = re.compile(
	r"(digite uma mensagem|type a message|escribe un mensaje|escribe un mensaje|"
	r"[eé]crivez un message|nachricht eingeben|scrivi un messaggio)",
	re.IGNORECASE,
)

LIST_ROLES = frozenset(r for r in (Role.TABLE, getattr(Role, "DATAGRID", None), Role.LIST) if r is not None)
ROW_ROLES = frozenset((Role.TABLEROW,))
CELL_ROLES = frozenset((Role.TABLECELL,))
# O foco do teclado numa conversa ou mensagem NÃO fica na linha (TABLEROW): fica
# num div focável DENTRO dela (tabIndex -1, sem papel; o NVDA o chama de SECTION).
# Código da página, 29/10/2026: a mensagem é ``role="row"`` com o div
# ``data-testid="conv-msg-..."`` focável e a fileira de botões (reagir, menu).
INNER_FOCUS_ROLES = frozenset((Role.SECTION,))
# Quantos níveis acima do div focável a linha pode estar.
ROW_SEARCH_LEVELS = 4

# Limites para que uma busca nunca congele o NVDA (thread principal).
# Um comando inteiro gasta no máximo COMMAND_SECONDS, não importa quantas
# caminhadas faça: todas dividem o mesmo prazo (``deadline``).
DEFAULT_BUDGET = 2500
DEFAULT_SECONDS = 0.25
COMMAND_SECONDS = 0.3


def new_deadline(seconds=COMMAND_SECONDS):
	"""Instante limite (time.monotonic) para um comando inteiro."""
	return time.monotonic() + seconds


def safe_role(obj):
	try:
		return obj.role
	except Exception:
		return None


def safe_states(obj):
	try:
		return obj.states
	except Exception:
		return set()


def safe_name(obj):
	try:
		return obj.name or ""
	except Exception:
		return ""


def safe_parent(obj):
	try:
		return obj.parent
	except Exception:
		return None


def has_state(obj, state):
	if state is None:
		return False
	return state in safe_states(obj)


def is_defunct(obj):
	"""True se o objeto sumiu da árvore (linha virtualizada que foi desmontada)."""
	try:
		states = obj.states
	except Exception:
		return True
	return State.DEFUNCT in states


def iter_children(obj, limit=None):
	"""Filhos de ``obj`` um a um (firstChild/next), sem montar a lista inteira."""
	try:
		child = obj.firstChild
	except Exception:
		return
	count = 0
	while child is not None:
		yield child
		count += 1
		if limit is not None and count >= limit:
			return
		try:
			child = child.next
		except Exception:
			return


def iter_children_reversed(obj, limit=None):
	try:
		child = obj.lastChild
	except Exception:
		return
	count = 0
	while child is not None:
		yield child
		count += 1
		if limit is not None and count >= limit:
			return
		try:
			child = child.previous
		except Exception:
			return


def walk(root, predicate, budget=DEFAULT_BUDGET, seconds=DEFAULT_SECONDS, skip=None, first=True, deadline=None):
	"""Busca em largura a partir de ``root``.

	Devolve o primeiro objeto que satisfaz ``predicate`` (``first=True``) ou a
	lista de todos. ``skip(obj)`` verdadeiro poda aquele ramo. O prazo é o
	menor entre ``seconds`` a partir de agora e ``deadline`` (instante absoluto,
	para vários passos de um mesmo comando dividirem o mesmo tempo).
	"""
	if root is None:
		return None if first else []
	found = []
	queue = [root]
	index = 0
	limit = time.monotonic() + seconds
	if deadline is not None:
		limit = min(limit, deadline)
	while index < len(queue) and index < budget:
		if time.monotonic() > limit:
			break
		obj = queue[index]
		index += 1
		try:
			if predicate(obj):
				if first:
					return obj
				found.append(obj)
			if skip is not None and skip(obj):
				continue
		except Exception:
			continue
		queue.extend(iter_children(obj))
	return None if first else found


def ancestors(obj, limit=12):
	"""Pais de ``obj``, do mais próximo ao mais distante."""
	current = safe_parent(obj)
	count = 0
	while current is not None and count < limit:
		yield current
		count += 1
		current = safe_parent(current)


def row_ancestor(obj, levels=ROW_SEARCH_LEVELS):
	"""A linha (TABLEROW) que contém ``obj``, até ``levels`` níveis acima, ou None.

	Se ``obj`` é o foco, usa a cadeia de ancestrais que o NVDA já montou para o
	foco (nenhuma chamada nova ao WhatsApp).
	"""
	try:
		focus = api.getFocusObject()
	except Exception:
		focus = None
	if focus is not None and obj is focus:
		try:
			chain = list(api.getFocusAncestors())
		except Exception:
			chain = []
		for parent in reversed(chain[-levels:]):
			if safe_role(parent) in ROW_ROLES:
				return parent
		return None
	for parent in ancestors(obj, levels):
		if safe_role(parent) in ROW_ROLES:
			return parent
	return None


def is_inner_focus(obj):
	"""Div focável de uma linha (o elemento que recebe o foco de verdade)."""
	if safe_role(obj) not in INNER_FOCUS_ROLES:
		return False
	return State.FOCUSABLE in safe_states(obj)


def focusable_in(row, budget=40):
	"""O elemento da linha que pode receber o foco: a própria linha, se focável, senão o div interno."""
	if row is None:
		return None
	if State.FOCUSABLE in safe_states(row):
		return row
	return walk(row, is_inner_focus, budget=budget, seconds=0.1)


def is_chat_list_container(obj):
	return safe_role(obj) in LIST_ROLES and bool(CHAT_LIST_RE.search(safe_name(obj)))


def chat_list_of(obj, limit=8):
	"""A lista de conversas que contém ``obj`` (ou o próprio ``obj``), ou None."""
	if is_chat_list_container(obj):
		return obj
	for parent in ancestors(obj, limit):
		if is_chat_list_container(parent):
			return parent
	return None


def is_composer(obj):
	"""Campo de digitação de mensagem (Lexical): editável, multilinha, não somente leitura."""
	if safe_role(obj) != Role.EDITABLETEXT:
		return False
	states = safe_states(obj)
	if State.READONLY in states:
		return False
	if State.MULTILINE in states:
		return True
	return bool(COMPOSER_NAME_RE.search(safe_name(obj)))


def find_composer(root, budget=1200, deadline=None):
	return walk(root, is_composer, budget=budget, deadline=deadline)


def find_chat_list(root, deadline=None):
	return walk(root, is_chat_list_container, deadline=deadline)


def rows_of(container, limit=400):
	"""Linhas (TABLEROW) de uma lista, achando-as até 3 níveis abaixo (rowgroup etc.)."""
	rows = []
	level = [container]
	for _depth in range(3):
		next_level = []
		for node in level:
			for child in iter_children(node, limit):
				if safe_role(child) in ROW_ROLES:
					rows.append(child)
					if len(rows) >= limit:
						return rows
				else:
					next_level.append(child)
		if rows:
			return rows
		level = next_level
		if not level:
			break
	return rows


def find_message_list(root, deadline=None):
	"""O contêiner das linhas de mensagem da conversa aberta, ou None.

	Parte do campo de digitação e sobe até um ancestral que tenha linhas fora
	da lista de conversas. O pai dessas linhas é a lista de mensagens. Todos os
	passos dividem o mesmo prazo.
	"""
	if deadline is None:
		deadline = new_deadline()
	composer = find_composer(root, deadline=deadline)
	if composer is None:
		return None
	for parent in ancestors(composer, 10):
		if time.monotonic() > deadline:
			return None
		row = walk(
			parent,
			lambda o: safe_role(o) in ROW_ROLES,
			budget=600,
			skip=is_chat_list_container,
			deadline=deadline,
		)
		if row is not None and chat_list_of(row) is None:
			return safe_parent(row)
	return None


def selected_or_first(rows):
	for row in rows:
		if State.SELECTED in safe_states(row):
			return row
	return rows[0] if rows else None


def document_root(focus=None, allow_foreground=False):
	"""A raiz do documento do WhatsApp onde está o foco (None se não achar).

	Usa a cadeia de ancestrais do foco, que o NVDA já tem pronta (sem chamadas
	ao WhatsApp). Só o aplicativo aceita a janela de primeiro plano como
	reserva (``allow_foreground``); no navegador isso seria varrer o Chrome todo.
	"""
	if focus is None:
		try:
			focus = api.getFocusObject()
		except Exception:
			return None
	root = None
	chain = []
	try:
		chain = list(api.getFocusAncestors())
	except Exception:
		chain = []
	chain.append(focus)
	for obj in chain:
		if safe_role(obj) == Role.DOCUMENT:
			root = obj
	if root is not None:
		return root
	if not allow_foreground:
		return None
	try:
		return api.getForegroundObject()
	except Exception:
		return None
