# -*- coding: UTF-8 -*-
"""Menus do WhatsApp (menu da mensagem e outros): as setas andam só pelas opções.

PROBLEMAS (relato do Leo, 30/10/2026, versão 2.0.1):
- Web: ao abrir o menu da mensagem o foco cai nas REAÇÕES, não em Responder,
  Copiar e as outras opções;
- aplicativo: descendo com a seta pelas opções, o foco escorrega para a
  mensagem de baixo e sai do menu.

CAUSA (código da página, 29/10/2026):
- o menu da mensagem (WAWebDropdown) agora começa com uma fileira de reações
  (WAWebWrapperMessageDropdownMenuReactionsTray). Para quem usa o teclado
  (``isKeyboardUser``) o menu foca o primeiro elemento com tabindex dentro
  dele, que é a primeira reação;
- as opções são itens ``li`` (papel botão) dentro de uma lista, ou, no menu
  novo (WDSMenu), botões com papel menuitem. O NVDA às vezes põe o foco no
  contêiner do menu (evento de início de menu) enquanto o foco do teclado
  continua na mensagem; aí a seta vai para a lista de mensagens.

SOLUÇÃO (a 1.4 resolvia no aplicativo com uma navegação própria pelo menu e
no Web levando o foco item a item; aqui é uma só para os dois):
- o menu é reconhecido UMA vez por evento de foco, pela cadeia de ancestrais
  do foco que o NVDA já tem pronta (nenhuma chamada nova ao WhatsApp);
- seta para baixo e para cima: o add-on leva o foco de verdade (``setFocus``)
  para a opção seguinte ou anterior, então o Enter seguinte vai para ela. Só
  em modo foco (ou sem buffer, como no aplicativo); em modo de navegação as
  setas continuam sendo do NVDA. Campo de texto dentro do menu (pesquisa do
  painel de emojis, por exemplo) fica com as setas;
- ao abrir, se o foco caiu numa reação ou no contêiner, vai direto para a
  primeira opção (opção "começar nas opções", ligada por padrão), sem falar
  a reação antes;
- seta para cima na primeira opção vai para a fileira de reações, se houver:
  reagir continua possível (Esquerda e Direita andam entre as reações);
- se o WhatsApp não aceitar o foco na opção (o aplicativo às vezes deixa o foco
  do NVDA no contêiner, por isso a 1.4 andava "por fora" no aplicativo), o
  add-on fala a opção e guarda a posição; a próxima seta continua dela e o
  Enter ativa a opção falada.
- Esc continua nativo (fecha o menu).
"""

import api
import core
import speech
from controlTypes import OutputReason

from . import diag, settings
from .tree import Role, State, iter_children, safe_role, safe_states, walk

MENU_ROLES = frozenset((Role.POPUPMENU, Role.MENU))
MENU_ITEM_ROLES = frozenset(
	r
	for r in (Role.MENUITEM, Role.CHECKMENUITEM, Role.RADIOMENUITEM)
	if r is not None
)
# Itens ``li`` do menu antigo (WAWebDropdownItem: papel "button" por padrão).
LIST_ITEM_ROLES = MENU_ITEM_ROLES | frozenset((Role.BUTTON, Role.LISTITEM, Role.TOGGLEBUTTON))
_CONTAINER_ROLES = MENU_ROLES | frozenset((Role.APPLICATION,))
# Até quantos ancestrais do foco o contêiner do menu pode estar.
MENU_SEARCH_LEVELS = 7
ITEM_BUDGET = 200
ITEM_SECONDS = 0.15
CHECK_DELAY_MS = 300
MOVE_CHECK_MS = 120  # tempo para o foco chegar à opção antes de andar "por fora"


class _Menu:
	container = None  # contêiner do menu em que o foco está (ou None)
	virtual = None  # opção falada "por fora" (o foco não foi para ela)
	virtual_from = None  # onde o foco estava quando a opção foi falada


def reset():
	_Menu.container = None
	_forget_virtual()


def _forget_virtual():
	_Menu.virtual = None
	_Menu.virtual_from = None


def active():
	"""O contêiner do menu do foco atual (calculado no último evento de foco), ou None."""
	return _Menu.container


def _is_editable(obj):
	return State.EDITABLE in safe_states(obj) or safe_role(obj) == Role.EDITABLETEXT


def _list_children(container):
	"""Listas filhas diretas do contêiner (o ``ul`` do menu antigo)."""
	return [child for child in iter_children(container, 10) if safe_role(child) == Role.LIST]


_HIDDEN = frozenset(s for s in (getattr(State, "UNAVAILABLE", None), getattr(State, "INVISIBLE", None)) if s is not None)


def _usable_item(obj, roles):
	if safe_role(obj) not in roles:
		return False
	return not (_HIDDEN & set(safe_states(obj)))


def items_of(container):
	"""As opções do menu, na ordem da tela. Reações e separadores ficam de fora.

	Menu novo: os itens com papel de item de menu. Menu antigo: os filhos
	diretos (papel botão) do próprio contêiner ou da lista ``ul`` dele; as
	reações ficam mais fundo, dentro de um div, e não entram.
	"""
	if container is None:
		return []
	found = walk(
		container,
		lambda o: _usable_item(o, MENU_ITEM_ROLES),
		budget=ITEM_BUDGET,
		seconds=ITEM_SECONDS,
		skip=lambda o: safe_role(o) in MENU_ITEM_ROLES,
		first=False,
	)
	if found:
		return found
	for holder in [container] + _list_children(container):
		items = [child for child in iter_children(holder, 60) if _usable_item(child, LIST_ITEM_ROLES)]
		if items:
			return items
	return []


def is_menu_container(obj):
	"""Contêiner de menu do WhatsApp: papel de menu, ou "application" com a lista de opções dentro."""
	role = safe_role(obj)
	if role in MENU_ROLES:
		return True
	if role != Role.APPLICATION:
		return False
	for holder in _list_children(obj):
		if any(_usable_item(child, LIST_ITEM_ROLES) for child in iter_children(holder, 60)):
			return True
	return False


def container_of(obj):
	"""O contêiner do menu que contém o foco ``obj`` (ou o próprio ``obj``), ou None.

	Usa a cadeia de ancestrais do foco que o NVDA já tem pronta.
	"""
	try:
		chain = list(api.getFocusAncestors())
	except Exception:
		chain = []
	chain = chain[-MENU_SEARCH_LEVELS:] + [obj]
	for candidate in reversed(chain):
		role = safe_role(candidate)
		if role == Role.DOCUMENT:
			return None  # o menu fica DENTRO do documento: acima dele não há o que procurar
		if role in _CONTAINER_ROLES and is_menu_container(candidate):
			return candidate
	return None


def tray_first(container, items):
	"""Primeiro botão do menu que não é uma opção (a fileira de reações), ou None."""

	def is_tray_button(obj):
		return safe_role(obj) == Role.BUTTON and obj not in items

	return walk(container, is_tray_button, budget=60, seconds=0.1)


def _index(items, obj):
	for index, item in enumerate(items):
		try:
			if item == obj:
				return index
		except Exception:
			continue
	return -1


def target_for(direction, focus=None):
	"""A opção que deve receber o foco com seta para baixo (1) ou para cima (-1), ou None."""
	container = _Menu.container
	items = items_of(container)
	if not items:
		return None
	if focus is None:
		focus = api.getFocusObject()
	index = _index(items, focus)
	if direction > 0:
		return items[index + 1] if 0 <= index < len(items) - 1 else items[0]
	if index > 0:
		return items[index - 1]
	if index == 0:
		return tray_first(container, items) or items[-1]
	return items[-1]


def _current(focus):
	"""A opção atual: a falada "por fora", se o foco ainda está onde estava; senão o foco."""
	if _Menu.virtual is not None and focus is not None and _Menu.virtual_from == focus:
		return _Menu.virtual
	return focus


def virtual_target(focus):
	"""A opção falada "por fora" que o Enter deve ativar, ou None."""
	if _Menu.container is None or _Menu.virtual is None or focus is None:
		return None
	return _Menu.virtual if _Menu.virtual_from == focus else None


def handles_arrows(focus):
	"""As setas são do add-on agora? Só no menu, fora de campo de texto e em modo foco."""
	if _Menu.container is None or focus is None:
		return False
	if _is_editable(focus):
		return False
	try:
		holder = focus.treeInterceptor
	except Exception:
		holder = None
	if holder is not None and not getattr(holder, "passThrough", True):
		return False  # modo de navegação: as setas são do NVDA
	return True


def move(direction, gesture):
	focus = api.getFocusObject()
	target = target_for(direction, _current(focus))
	if target is None:
		gesture.send()
		return
	try:
		target.setFocus()
	except Exception:
		pass
	core.callLater(MOVE_CHECK_MS, _check_followed, focus, target)


def _check_followed(origin, target):
	"""O foco não foi para a opção? Anda "por fora": fala a opção e guarda a posição."""
	try:
		if api.getFocusObject() != origin:
			return  # o foco andou: o NVDA já falou a opção
		_Menu.virtual = target
		_Menu.virtual_from = origin
		diag.act("menu-por-fora", diag.describe(target))
		speech.speakObject(target, reason=OutputReason.FOCUS)
	except Exception:
		pass


def activate(gesture):
	"""Enter com uma opção falada "por fora": ativa essa opção."""
	target = virtual_target(api.getFocusObject())
	if target is None:
		gesture.send()
		return
	_forget_virtual()
	try:
		target.doAction()
	except Exception:
		gesture.send()


# ─── evento de foco ─────────────────────────────────────────────────────────

def _silent_report():
	"""Substitui ``reportFocus`` da reação enquanto o foco vai para a primeira opção."""


def handle_gain_focus(obj, nextHandler):
	"""Chamado pelo plugin global em todo evento de foco do WhatsApp.

	Atualiza o menu do foco. Se o foco ACABOU de entrar num menu e caiu numa
	reação ou no contêiner, leva-o à primeira opção sem falar a reação.
	Devolve True se tratou o evento (não chame ``nextHandler`` de novo).
	"""
	previous = _Menu.container
	_forget_virtual()  # foco de verdade mudou: a posição "por fora" não vale mais
	container = container_of(obj)
	_Menu.container = container
	if container is None:
		return False
	entering = previous is None or not (previous == container)
	if not entering or not settings.get("menuStartOnOptions") or _is_editable(obj):
		return False
	items = items_of(container)
	if not items or _index(items, obj) >= 0:
		return False
	first = items[0]
	diag.act("menu-primeira-opcao", diag.describe(obj))
	obj.reportFocus = _silent_report
	try:
		nextHandler()
	finally:
		try:
			del obj.reportFocus
		except Exception:
			pass
	try:
		first.setFocus()
	except Exception:
		pass
	core.callLater(CHECK_DELAY_MS, _check_moved, obj)
	return True


def _check_moved(obj):
	"""O foco não saiu da reação (o WhatsApp não aceitou)? Então fala onde ele está."""
	try:
		if api.getFocusObject() == obj:
			speech.speakObject(obj, reason=OutputReason.FOCUS)
	except Exception:
		pass
