class _Section(dict):
	pass


class _Conf(dict):
	def __init__(self):
		super().__init__()
		self.spec = {}
		self.saved = 0
		self.reset()

	def reset(self):
		self.clear()
		self["virtualBuffers"] = {
			"autoPassThroughOnFocusChange": True,
			"autoPassThroughOnCaretMove": False,
			"passThroughAudioIndication": True,
		}
		self.saved = 0

	def save(self):
		self.saved += 1


conf = _Conf()
