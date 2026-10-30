# -*- coding: UTF-8 -*-
"""Texto, botões e player de uma mensagem do WhatsApp.

Reaproveitado da 1.4.x: a espera do "ler mais" (confere o texto a cada 60 ms) e
a busca do player de áudio (controle deslizante + botões que vêm antes dele).
O resto foi reescrito para procurar pela estrutura (papel + nome) a partir da
própria linha da mensagem, em vez de pelos "irmãos" do foco.
"""

import re

import controlTypes
import core

from .tree import (
	Role,
	is_chat_list_container,
	iter_children,
	safe_name,
	safe_role,
	safe_states,
	walk,
)

# O botão "Ler mais" não tem aria-expanded: acha-se por papel BOTÃO + nome.
READ_MORE_RE = re.compile(
	r"^\s*(ler mais|read more|leer m[aá]s|lire la suite|voir plus|mehr anzeigen|"
	r"leggi tutto|devamını oku)\s*$",
	re.IGNORECASE,
)
# Quando o texto está cortado, o nome da mensagem termina com "… Ler mais".
READ_MORE_SUFFIX_RE = re.compile(
	r"[….]{1,3}\s*(ler mais|read more|leer m[aá]s|lire la suite|voir plus)\s*$",
	re.IGNORECASE,
)
MENU_BUTTON_RE = re.compile(
	r"^\s*(menu|mais op[cç][oõ]es|more options|op[cç][oõ]es( da mensagem)?|message options|"
	r"m[aá]s opciones|opciones del mensaje|plus d.options)\b",
	re.IGNORECASE,
)
REACT_BUTTON_RE = re.compile(r"(reagir|react|reaccionar|r[eé]agir)", re.IGNORECASE)
CALL_BUTTON_RE = re.compile(r"(chamada|ligar|\bcall\b|llamada|appel|anruf)", re.IGNORECASE)
SPEED_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*[x×]\s*$", re.IGNORECASE)
DURATION_RE = re.compile(r"\b\d+:\d{2}\b")

# Espera do "ler mais": confere o texto a cada 60 ms, até 21 vezes (1,26 s).
EXPAND_DELAY_MS = 60
EXPAND_MAX_TRIES = 20

TEXT_BUDGET = 400


def collect_texts(obj, min_length=2, budget=TEXT_BUDGET):
	"""Textos (STATICTEXT) da mensagem, na ordem da tela (profundidade primeiro)."""
	texts = []
	counter = [0]

	def visit(node):
		if counter[0] >= budget:
			return
		counter[0] += 1
		try:
			if safe_role(node) == Role.STATICTEXT:
				name = safe_name(node).strip()
				if len(name) >= min_length:
					texts.append(name)
			for child in iter_children(node):
				visit(child)
		except Exception:
			return

	visit(obj)
	return texts


def message_text(row):
	"""Texto da mensagem.

	Usa o nome da linha quando ele está completo. Se estiver cortado ("… Ler
	mais") ou vazio, usa o texto dos descendentes. Nome vazio é normal: sem uso
	do teclado recente o WhatsApp tira o aria-label das mensagens.
	"""
	name = safe_name(row).strip()
	cleaned = READ_MORE_SUFFIX_RE.sub("", name).strip()
	if name and cleaned == name:
		return name
	body = " ".join(collect_texts(row))
	return body if len(body) > len(cleaned) else cleaned


def is_truncated(row):
	name = safe_name(row).strip()
	return bool(READ_MORE_SUFFIX_RE.search(name)) or find_read_more(row) is not None


def find_buttons(root, predicate=None, budget=TEXT_BUDGET, first=False):
	def is_button(obj):
		if safe_role(obj) != Role.BUTTON:
			return False
		return predicate is None or predicate(obj)

	return walk(root, is_button, budget=budget, seconds=1.0, first=first)


def find_read_more(row):
	return find_buttons(row, lambda b: bool(READ_MORE_RE.match(safe_name(b))), first=True)


def expand_then(row, callback):
	"""Clica em "ler mais" e entrega o texto já expandido.

	A expansão acontece dentro do WhatsApp, em outro processo, então o texto
	novo não está disponível na hora. Em vez de esperar um tempo fixo, confere
	o texto a cada 60 ms e entrega assim que ele cresce. Se não crescer no
	prazo (WhatsApp lento), entrega o que houver, para a tecla nunca ficar sem
	resposta.
	"""
	button = find_read_more(row)
	before = message_text(row)
	if button is None:
		callback(before)
		return
	try:
		button.doAction()
	except Exception:
		# O elemento pode sumir entre procurar e clicar (mensagem nova chegando,
		# lista rolando). Nesse caso fala o que já está visível.
		callback(before)
		return

	def poll(tries_left):
		current = message_text(row)
		if len(current) > len(before) or tries_left <= 0:
			callback(current)
			return
		core.callLater(EXPAND_DELAY_MS, poll, tries_left - 1)

	core.callLater(EXPAND_DELAY_MS, poll, EXPAND_MAX_TRIES)


# ─── Player de áudio e vídeo ────────────────────────────────────────────────

def _buttons_before(row, stop):
	"""Botões da linha, em ordem de leitura, até chegar em ``stop``."""
	buttons = []
	counter = [0]
	done = [False]

	def visit(node):
		if done[0] or counter[0] >= TEXT_BUDGET:
			return
		counter[0] += 1
		if node == stop:
			done[0] = True
			return
		if safe_role(node) == Role.BUTTON:
			buttons.append(node)
		for child in iter_children(node):
			visit(child)
			if done[0]:
				return

	visit(row)
	return buttons


def find_player(row):
	"""(botões antes da barra de posição, barra de posição) do áudio da mensagem.

	Não usa nome de classe do site. Sem barra de posição: ([], None).
	"""
	slider = walk(
		row,
		lambda o: safe_role(o) in (Role.SLIDER, Role.PROGRESSBAR),
		budget=TEXT_BUDGET,
		seconds=1.0,
	)
	if slider is None:
		return [], None
	return _buttons_before(row, slider), slider


def find_video_button(row):
	"""Botão de reproduzir de um vídeo (o rótulo tem a duração, como 0:45)."""
	return find_buttons(row, lambda b: bool(DURATION_RE.search(safe_name(b))), first=True)


def play_target(row):
	"""Botão que toca/pausa a mensagem, ou None se ela não tem player."""
	buttons, slider = find_player(row)
	if slider is not None and buttons:
		return buttons[-1]
	return find_video_button(row)


def speed_target(row):
	buttons, slider = find_player(row)
	if slider is None:
		return None
	for button in reversed(buttons):
		name = safe_name(button).strip()
		try:
			value = str(button.value or "").strip()
		except Exception:
			value = ""
		if SPEED_RE.match(name) or SPEED_RE.match(value):
			return button
	# Sem rótulo de velocidade: no player do WhatsApp ele é o botão
	# imediatamente antes do play/pause.
	if len(buttons) >= 2:
		return buttons[-2]
	return None


def menu_button(row):
	button = find_buttons(row, lambda b: bool(MENU_BUTTON_RE.match(safe_name(b))), first=True)
	if button is not None:
		return button
	collapsed = getattr(controlTypes.State, "COLLAPSED", None)
	return find_buttons(row, lambda b: collapsed in safe_states(b), first=True)


def react_button(row):
	return find_buttons(row, lambda b: bool(REACT_BUTTON_RE.search(safe_name(b))), first=True)


def call_button(root):
	"""Botão de chamada do cabeçalho da conversa (fora da lista de conversas)."""

	def is_call(obj):
		return safe_role(obj) == Role.BUTTON and bool(CALL_BUTTON_RE.search(safe_name(obj)))

	return walk(root, is_call, skip=is_chat_list_container)
