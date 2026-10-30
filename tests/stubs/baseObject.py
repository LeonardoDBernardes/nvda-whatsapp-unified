"""Stub minimo de baseObject: propriedades automaticas (_get_/_set_) como no NVDA e resolucao de gestos."""


class _Getter:
	"""Como o ``Getter`` do NVDA: so leitura, e atribuir a instancia substitui a propriedade."""

	def __init__(self, fget):
		self.fget = fget

	def __get__(self, instance, owner=None):
		if instance is None:
			return self
		return self.fget(instance)


class AutoPropertyType(type):
	def __init__(cls, name, bases, namespace, **kwargs):
		super().__init__(name, bases, namespace, **kwargs)
		names = {key[5:] for key in namespace if key[:5] in ("_get_", "_set_")}
		for item in names:
			getter = namespace.get("_get_" + item)
			setter = namespace.get("_set_" + item)
			if getter is None:
				for base in bases:
					getter = getattr(base, "_get_" + item, None)
					if getter is not None:
						break
			if getter is not None and setter is None:
				setattr(cls, item, _Getter(getter))
			else:
				setattr(cls, item, property(getter, setter))


class AutoPropertyObject(metaclass=AutoPropertyType):
	pass


class ScriptableObject(AutoPropertyObject):
	def getScript(self, gesture):
		wanted = set(getattr(gesture, "identifiers", ()))
		for klass in type(self).__mro__:
			for attr, func in vars(klass).items():
				if not attr.startswith("script_"):
					continue
				if wanted.intersection(getattr(func, "wa_gestures", ())):
					return getattr(self, attr)
		return None
