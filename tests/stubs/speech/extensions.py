class _Filter:
	def __init__(self):
		self.handlers = []

	def register(self, handler):
		self.handlers.append(handler)

	def unregister(self, handler):
		self.handlers.remove(handler)

	def apply(self, value):
		for handler in self.handlers:
			value = handler(value)
		return value


filter_speechSequence = _Filter()
