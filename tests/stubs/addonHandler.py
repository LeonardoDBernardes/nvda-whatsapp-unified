import builtins


def initTranslation():
	builtins.__dict__["_"] = lambda text: text
