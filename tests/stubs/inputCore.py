class _Decider:
	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		self.handlers.remove(handler)

	def decide(self, **kwargs):
		return all(h(**kwargs) for h in self.handlers)


decide_handleRawKey = _Decider()


def normalizeGestureIdentifier(identifier):
	"""Como o NVDA: minúsculas e modificadores em ordem alfabética (ex.: kb:control+shift+enter)."""
	prefix, _sep, rest = identifier.lower().partition(":")
	parts = rest.split("+")
	return prefix + ":" + "+".join(sorted(parts[:-1]) + parts[-1:])
