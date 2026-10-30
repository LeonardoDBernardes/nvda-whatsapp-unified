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
