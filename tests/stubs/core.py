"""Stub de core.callLater: guarda as chamadas; o teste decide quando executar."""

pending = []


def callLater(delay, callable, *args, **kwargs):
	pending.append((delay, callable, args, kwargs))
	return len(pending)


def run_pending(limit=100):
	"""Executa (em ordem) o que foi agendado, inclusive o que for agendado no caminho."""
	count = 0
	while pending and count < limit:
		_delay, func, args, kwargs = pending.pop(0)
		func(*args, **kwargs)
		count += 1
	return count


def reset():
	pending.clear()
