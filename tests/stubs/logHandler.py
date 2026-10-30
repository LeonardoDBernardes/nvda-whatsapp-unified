class _Log:
	def __init__(self):
		self.lines = []

	def debugWarning(self, *a, **k):
		pass

	def error(self, *a, **k):
		pass

	def exception(self, *a, **k):
		pass

	def info(self, message, *a, **k):
		self.lines.append(str(message))


log = _Log()
