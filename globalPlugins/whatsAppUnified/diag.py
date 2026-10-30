# -*- coding: UTF-8 -*-
"""Diagnóstico: registra no log do NVDA (nível INFO) SEMPRE que o add-on age.

Serve para descobrir "o add-on está mexendo em algo fora do WhatsApp?". Cada
linha começa com ``WhatsAppUnificado:`` e diz o que o add-on fez (overlay
aplicado, foco adiado ou recuperado, script executado, fala filtrada, modo foco
fixado ou solto). Limites, para o log não encher:
- no máximo uma linha por ação (e por classe, no caso de sobreposição) a cada 2 segundos;
- gancho do add-on que demora mais de 100 ms vira uma linha "lento" (com o tempo);
- no máximo 200 linhas por sessão do NVDA (a 201ª é só o aviso de que parou).
NUNCA registra conteúdo de mensagem: só papel, nome de classe, nome do programa
e o TAMANHO de um texto. A opção "Registrar ações no log do NVDA (diagnóstico)"
liga e desliga isto (ligada por padrão nesta versão de teste).
"""

import functools
import time

from logHandler import log

from . import settings

PREFIX = "WhatsAppUnificado:"
MIN_GAP_S = 2.0
MAX_LINES = 200


class _Counter:
	lines = 0
	last = {}
	stopped = False


def reset():
	_Counter.lines = 0
	_Counter.last = {}
	_Counter.stopped = False


def lines_written():
	return _Counter.lines


def act(action, detail="", key=None):
	"""Registra uma ação do add-on (com os limites acima). Nunca levanta exceção."""
	try:
		if not settings.get("diagLog"):
			return
		if _Counter.stopped:
			return
		if _Counter.lines >= MAX_LINES:
			_Counter.stopped = True
			log.info("%s limite de %d linhas de diagnóstico atingido; parei de registrar" % (PREFIX, MAX_LINES))
			return
		now = time.monotonic()
		key = key or action
		previous = _Counter.last.get(key)
		if previous is not None and now - previous < MIN_GAP_S:
			return
		_Counter.last[key] = now
		_Counter.lines += 1
		log.info(("%s %s %s" % (PREFIX, action, detail)).rstrip())
	except Exception:
		pass


# Um gancho do add-on que passa disto vira uma linha "lento" no log: serve para
# separar "o add-on atrasou" de "o WhatsApp ou o navegador travou".
SLOW_S = 0.1


def slow(what, started, obj=None):
	"""Registra ``what`` como lento se passou de SLOW_S desde ``started`` (time.monotonic)."""
	try:
		elapsed = time.monotonic() - started
		if elapsed < SLOW_S:
			return
		detail = "%s %d ms" % (what, int(elapsed * 1000))
		if obj is not None:
			detail += " " + describe(obj)
		act("lento", detail, key="lento:" + what)
	except Exception:
		pass


def role_name(obj):
	"""Papel do objeto como texto curto (nunca o nome nem o valor)."""
	try:
		role = obj.role
		return str(getattr(role, "name", role))
	except Exception:
		return "?"


def describe(obj):
	"""``programa/papel`` do objeto, para as linhas de diagnóstico."""
	from .context import app_name_of

	return "app=%s papel=%s" % (app_name_of(obj) or "?", role_name(obj))


def scripted(func):
	"""Decorador: registra que um script do add-on foi executado (só o nome do script)."""

	@functools.wraps(func)
	def wrapper(self, gesture, *args, **kwargs):
		name = func.__name__
		act("script", name.replace("script_", ""), key="script:" + name)
		started = time.monotonic()
		try:
			return func(self, gesture, *args, **kwargs)
		finally:
			slow("script:" + name.replace("script_", ""), started)

	return wrapper
