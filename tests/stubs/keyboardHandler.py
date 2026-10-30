sent = []


class KeyboardInputGesture:
	def __init__(self, name):
		self.name = name

	@classmethod
	def fromName(cls, name):
		return cls(name)

	def send(self):
		sent.append(self.name)
