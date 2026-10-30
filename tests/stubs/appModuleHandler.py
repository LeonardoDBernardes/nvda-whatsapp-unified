from baseObject import ScriptableObject


class AppModule(ScriptableObject):
	appName = "stub"
	disableBrowseModeByDefault = False

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		pass
