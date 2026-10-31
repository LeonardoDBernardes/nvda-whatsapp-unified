#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Verificador estatico (ast) das APIs do NVDA que o add-on usa.

Nada e importado nem executado: o codigo-fonte do NVDA e lido como texto e analisado com ``ast``.
Confere, no codigo-fonte do NVDA 2026.2:

1. cada ``import X`` / ``from X import Y`` do add-on aponta para um modulo e um nome que existem;
2. cada acesso estatico ``modulo.nome`` (e ``Classe.membro`` quando a classe e resolvivel),
   inclusive ``modulo.objeto.metodo`` quando o objeto e criado por uma classe do NVDA
   (por exemplo ``filter_speechSequence.register``);
3. cada ``super().metodo`` dentro de uma classe que herda de classe do NVDA existe na cadeia de bases;
4. os argumentos de chamadas a funcoes do NVDA (nomes de palavras-chave e quantidade de posicionais);
5. uma lista de atributos de instancia que o add-on le dos objetos do NVDA
   (``obj.firstChild``, ``treeInterceptor.passThrough`` ...), conferidos nas classes do NVDA;
6. os imports e nomes relativos entre os modulos do proprio add-on.

Uso:  python3 tests/check_nvda_api.py [--fonte CAMINHO]
O caminho padrao e a variavel NVDA_SRC ou
/tmp/claude-1000/-home-leo/9a720e18-e9eb-42b8-909c-5ae444a2765f/scratchpad/nvda-src/nvda/source
(o codigo do NVDA 2026.2). Sai com codigo 0 se tudo confere, 1 se algo nao existe.
"""

import argparse
import ast
import os
import sys

DEFAULT_SRC = os.environ.get(
	"NVDA_SRC",
	"/tmp/claude-1000/-home-leo/9a720e18-e9eb-42b8-909c-5ae444a2765f/scratchpad/nvda-src/nvda/source",
)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIRS = ("globalPlugins", "appModules")

# Bibliotecas de terceiros que o NVDA traz mas que nao estao no codigo-fonte dele.
EXTERNAL = {"wx"}

# Atributos de instancia que o add-on le dos objetos do NVDA: classe -> nomes.
# (Instancias nao sao resolviveis por ast; aqui conferimos que o NVDA os define.)
INSTANCE_ATTRS = {
	("NVDAObjects.IAccessible", "IAccessible"): [
		"role", "name", "states", "parent", "firstChild", "lastChild", "next", "previous",
		"location", "positionInfo", "windowHandle", "windowClassName", "IA2UniqueID",
		"IAccessibleObject", "IAccessibleRole", "appModule", "treeInterceptor", "isFocusable",
		"value", "setFocus", "doAction", "reportFocus", "activeChild", "focusRedirect",
		"IA2Attributes", "event_gainFocus", "windowHandle",
		"shouldAllowIAccessibleMenuStartEvent", "treeInterceptorClass", "getScript",
		"shouldCreateTreeInterceptor",
	],
	("NVDAObjects.IAccessible.chromium", "ChromeVBuf"): [
		"rootNVDAObject", "documentConstantIdentifier", "documentURL", "passThrough",
		"disableAutoPassThrough", "_disableAutoPassThrough", "_passThrough",
		"shouldPassThrough", "event_treeInterceptor_gainFocus", "event_gainFocus",
		"script_disablePassThrough", "isReady",
	],
	("appModuleHandler", "AppModule"): [
		"appName", "chooseNVDAObjectOverlayClasses", "getScript",
	],
	("globalPluginHandler", "GlobalPlugin"): [
		"terminate", "chooseNVDAObjectOverlayClasses", "getScript",
	],
	("gui.settingsDialogs", "NVDASettingsDialog"): ["categoryClasses"],
	("gui.settingsDialogs", "SettingsPanel"): ["makeSettings", "onSave", "title"],
}

# Ganchos que o NVDA procura por NOME (getattr / __dict__), sem existir na classe base.
# (arquivo, trecho que deve existir no codigo-fonte do NVDA, o que o add-on faz com isso)
HOOKS = [
	("NVDAObjects/__init__.py", 'cls.__dict__.get("initOverlayClass")',
	 "initOverlayClass definido DENTRO de cada classe de sobreposicao"),
	("treeInterceptorHandler.py", 'getattr(obj.appModule, "disableBrowseModeByDefault", False)',
	 "AppModule.disableBrowseModeByDefault = True"),
	("eventHandler.py", 'getattr(func, "ignoreIsReady", False)',
	 "event_gainFocus.ignoreIsReady = True"),
	("baseObject.py", "@cvar scriptCategory", "scriptCategory nas classes de scripts"),
	("baseObject.py", "_cache_", "_cache_focusRedirect = True"),
	("browseMode.py", "reportPassThrough.last = False", "browseMode.reportPassThrough.last (variavel global)"),
	("browseMode.py", "reportPassThrough.last = treeInterceptor.passThrough",
	 "o NVDA compara/atualiza reportPassThrough.last"),
	("virtualBuffers/MSHTML.py", "_passThrough = True",
	 "precedente do NVDA: _passThrough/_disableAutoPassThrough fixados no construtor"),
	("virtualBuffers/MSHTML.py", "disableAutoPassThrough = True", "idem (MSHTML)"),
	("NVDAObjects/IAccessible/ia2Web.py", "iaRole in (oleacc.ROLE_SYSTEM_APPLICATION, oleacc.ROLE_SYSTEM_DIALOG) or (",
	 "todo diálogo web ganha a classe de documento (WhatsAppMenuDialog)"),
	("treeInterceptorHandler.py", "if not obj.shouldCreateTreeInterceptor and not force:",
	 "WhatsAppMenuDialog.shouldCreateTreeInterceptor = False impede o buffer próprio"),
]

# Variaveis de modulo que o NVDA preenche em tempo de execucao (valem None no codigo-fonte):
# (modulo, nome) -> (modulo, classe da instancia)
DYNAMIC_INSTANCES = {
	("config", "conf"): ("config", "ConfigManager"),
	("logHandler", "log"): ("logHandler", "Logger"),
}

problems = []
unchecked = []
verified = []


def fail(where, text):
	problems.append("%s: %s" % (where, text))


def note(text):
	verified.append(text)


# ─── leitura do codigo-fonte do NVDA ────────────────────────────────────────

_ast_cache = {}


def module_file(src, dotted):
	"""Arquivo .py de um modulo (ou __init__.py de um pacote) do NVDA, ou None."""
	parts = dotted.split(".")
	if parts[0] == "nvdaBuiltin" and len(parts) > 1:
		parts = parts[1:]  # nvdaBuiltin.__path__ aponta para a propria pasta do codigo-fonte
	base = os.path.join(src, *parts)
	if os.path.isfile(base + ".py"):
		return base + ".py"
	if os.path.isfile(os.path.join(base, "__init__.py")):
		return os.path.join(base, "__init__.py")
	if os.path.isfile(base + ".pyi"):
		return base + ".pyi"
	return None


def is_package_file(path):
	return os.path.basename(path) == "__init__.py"


def parse(path):
	if path not in _ast_cache:
		with open(path, encoding="utf-8") as handle:
			_ast_cache[path] = ast.parse(handle.read(), path)
	return _ast_cache[path]


def dotted_of(src, path):
	rel = os.path.relpath(path, src)[:-3].replace(os.sep, ".")
	return rel[: -len(".__init__")] if rel.endswith(".__init__") else rel


def resolve_relative(src, path, level, module):
	pkg = dotted_of(src, path)
	if not is_package_file(path):
		pkg = pkg.rsplit(".", 1)[0] if "." in pkg else ""
	parts = pkg.split(".") if pkg else []
	if level > 1:
		parts = parts[: len(parts) - (level - 1)]
	if module:
		parts += module.split(".")
	return ".".join(parts)


class Namespace:
	"""Nomes de nivel de modulo de um arquivo: definicoes, atribuicoes e importacoes."""

	def __init__(self, src, path):
		self.src = src
		self.path = path
		self.names = {}  # nome -> ("class"|"func"|"assign"|"import"|"from", dado)
		self.star = []  # modulos importados com *
		self.func_attrs = set()  # (nome, atributo) de ``f.x = ...`` no nivel do modulo
		self.all = None
		tree = parse(path)
		self._collect(tree.body)

	def _collect(self, body):
		for node in body:
			if isinstance(node, ast.ClassDef):
				self.names[node.name] = ("class", node)
			elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
				self.names[node.name] = ("func", node)
			elif isinstance(node, ast.Assign):
				for target in node.targets:
					if isinstance(target, ast.Name):
						self.names[target.id] = ("assign", node.value)
						if target.id == "__all__":
							try:
								self.all = set(ast.literal_eval(node.value))
							except Exception:
								pass
					elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
						self.func_attrs.add((target.value.id, target.attr))
			elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
				self.names[node.target.id] = ("assign", node.value)
			elif isinstance(node, ast.Import):
				for alias in node.names:
					bound = alias.asname or alias.name.split(".")[0]
					self.names[bound] = ("import", alias.name if alias.asname else bound)
			elif isinstance(node, ast.ImportFrom):
				if node.level:
					module = resolve_relative(self.src, self.path, node.level, node.module)
				else:
					module = node.module or ""
				for alias in node.names:
					if alias.name == "*":
						self.star.append(module)
					else:
						self.names[alias.asname or alias.name] = ("from", (module, alias.name))
			elif isinstance(node, (ast.If, ast.Try)):
				# Importacoes e definicoes condicionais tambem contam.
				for branch in (getattr(node, "body", []), getattr(node, "orelse", [])):
					self._collect(branch)
				for handler in getattr(node, "handlers", []):
					self._collect(handler.body)
				self._collect(getattr(node, "finalbody", []))


_ns_cache = {}


def namespace(src, path):
	key = (src, path)
	if key not in _ns_cache:
		_ns_cache[key] = Namespace(src, path)
	return _ns_cache[key]


def has_submodule(src, dotted, name):
	return module_file(src, dotted + "." + name) is not None


def lookup(src, dotted, name, depth=0):
	"""Resolve ``name`` no modulo ``dotted``. Devolve (tipo, dado, caminho) ou None.

	tipo: "module", "class", "func", "assign" (dado = arquivo/no).
	"""
	if depth > 12:
		return None
	path = module_file(src, dotted)
	if path is None:
		return None
	ns = namespace(src, path)
	if name in ns.names:
		kind, data = ns.names[name]
		if kind in ("class", "func", "assign"):
			return (kind, data, path)
		if kind == "from":
			module, original = data
			return lookup_in(src, module, original, depth + 1)
		if kind == "import":
			target = module_file(src, data)
			return ("module", target, target) if target else None
	for module in ns.star:
		found = lookup_public(src, module, name, depth + 1)
		if found:
			return found
	if is_package_file(path) and has_submodule(src, dotted, name):
		sub = module_file(src, dotted + "." + name)
		return ("module", sub, sub)
	return None


def lookup_in(src, module, name, depth):
	found = lookup(src, module, name, depth)
	if found:
		return found
	if has_submodule(src, module, name):
		sub = module_file(src, module + "." + name)
		return ("module", sub, sub)
	return None


def lookup_public(src, module, name, depth):
	path = module_file(src, module)
	if path is None:
		return None
	ns = namespace(src, path)
	if ns.all is not None and name not in ns.all:
		return None
	if name.startswith("_") and ns.all is None:
		return None
	return lookup(src, module, name, depth)


# ─── classes e seus membros ─────────────────────────────────────────────────

def base_names(node):
	return node.bases


def class_own_members(node):
	"""Nomes definidos pela propria classe, mais ``self.x = ...`` dos metodos."""
	members = set()
	for item in node.body:
		if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
			members.add(item.name)
			if item.name[:5] in ("_get_", "_set_", "_del_"):
				members.add(item.name[5:])
			if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
				for sub in ast.walk(item):
					if isinstance(sub, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
						targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
						for target in targets:
							if (
								isinstance(target, ast.Attribute)
								and isinstance(target.value, ast.Name)
								and target.value.id == "self"
							):
								members.add(target.attr)
		elif isinstance(item, ast.Assign):
			for target in item.targets:
				if isinstance(target, ast.Name):
					members.add(target.id)
				elif isinstance(target, ast.Tuple):
					members.update(e.id for e in target.elts if isinstance(e, ast.Name))
		elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
			members.add(item.target.id)
		elif isinstance(item, (ast.If, ast.Try)):
			wrapper = ast.ClassDef(name=node.name, bases=[], keywords=[], body=item.body, decorator_list=[])
			members |= class_own_members(wrapper)
	return members


def resolve_expr(src, path, expr, depth=0):
	"""Resolve ``Nome`` / ``mod.Nome`` / ``Nome[...]`` para (tipo, dado, caminho) ou None."""
	if depth > 8:
		return None
	if isinstance(expr, ast.Subscript):
		return resolve_expr(src, path, expr.value, depth + 1)
	ns = namespace(src, path)
	if isinstance(expr, ast.Name):
		if expr.id in ns.names:
			kind, data = ns.names[expr.id]
			if kind in ("class", "func", "assign"):
				return (kind, data, path)
			if kind == "from":
				return lookup_in(src, data[0], data[1], depth + 1)
			if kind == "import":
				target = module_file(src, data)
				return ("module", target, target) if target else None
		for module in ns.star:
			found = lookup_public(src, module, expr.id, depth + 1)
			if found:
				return found
		return None
	if isinstance(expr, ast.Attribute):
		base = resolve_expr(src, path, expr.value, depth + 1)
		if base and base[0] == "module":
			return lookup(src, dotted_of(src, base[1]), expr.attr, depth + 1)
	return None


def stdlib_members(src, path, expr):
	"""Membros de uma classe da biblioteca padrao usada como base (ex.: enum.IntEnum, abc.ABC)."""
	import importlib

	ns = namespace(src, path)
	module = name = None
	if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
		entry = ns.names.get(expr.value.id)
		if entry and entry[0] == "import" and entry[1].split(".")[0] in sys.stdlib_module_names:
			module, name = entry[1], expr.attr
	elif isinstance(expr, ast.Name):
		entry = ns.names.get(expr.id)
		if entry and entry[0] == "from" and entry[1][0].split(".")[0] in sys.stdlib_module_names:
			module, name = entry[1]
	if module is None:
		return None
	try:
		return set(dir(getattr(importlib.import_module(module), name)))
	except Exception:
		return None


class ClassInfo:
	def __init__(self, src, path, node):
		self.src, self.path, self.node = src, path, node
		self.complete = True  # todas as bases foram resolvidas?
		self.members = set(class_own_members(node))
		self.chain = [node.name]
		for base in node.bases:
			target = resolve_expr(src, path, base)
			if target and target[0] == "class":
				sub = ClassInfo(src, target[2], target[1])
				self.members |= sub.members
				self.complete = self.complete and sub.complete
				self.chain += sub.chain
			elif isinstance(base, ast.Name) and base.id in ("object", "Exception", "dict", "list", "int", "str"):
				self.members |= set(dir(__builtins__[base.id] if isinstance(__builtins__, dict) else getattr(__builtins__, base.id)))
			elif stdlib_members(src, path, base) is not None:
				self.members |= stdlib_members(src, path, base)
			elif target and target[0] == "assign":
				self.complete = False  # base dinamica
			else:
				self.complete = False
		for keyword in node.keywords:
			if keyword.arg == "metaclass":
				continue

	def has(self, name):
		return (
			name in self.members
			or ("_get_" + name) in self.members
			or ("_set_" + name) in self.members
			or name in ("__init__", "__class__", "__doc__", "__name__", "__dict__", "__module__")
		)


def instance_class(src, found):
	"""Se ``found`` e uma atribuicao ``x = Classe(...)`` ou ``Classe[...](...)``, a classe de ``x``."""
	kind, data, path = found
	if kind != "assign" or not isinstance(data, ast.Call):
		return None
	target = resolve_expr(src, path, data.func)
	if target and target[0] == "class":
		return ClassInfo(src, target[2], target[1])
	return None


# ─── verificacao do codigo do add-on ────────────────────────────────────────

def addon_files():
	for top in ADDON_DIRS:
		for base, _dirs, files in os.walk(os.path.join(ROOT, top)):
			if "__pycache__" in base:
				continue
			for name in sorted(files):
				if name.endswith(".py"):
					yield os.path.join(base, name)


def addon_module_name(path):
	rel = os.path.relpath(path, ROOT)[:-3].replace(os.sep, ".")
	return rel[: -len(".__init__")] if rel.endswith(".__init__") else rel


def addon_module_file(dotted):
	parts = dotted.split(".")
	base = os.path.join(ROOT, *parts)
	if os.path.isfile(base + ".py"):
		return base + ".py"
	if os.path.isfile(os.path.join(base, "__init__.py")):
		return os.path.join(base, "__init__.py")
	if os.path.isdir(base):
		return base  # pacote de espaco de nomes (globalPlugins/)
	return None


def addon_names(path):
	if os.path.isdir(path):
		return None
	return namespace(ROOT, path)


class FileChecker(ast.NodeVisitor):
	def __init__(self, src, path):
		self.src = src
		self.path = path
		self.rel = os.path.relpath(path, ROOT)
		self.aliases = {}  # nome local -> ("module", dotted) | ("sym", (tipo, dado, arquivo))
		self.class_stack = []
		self.tree = parse(path)
		self.here = addon_module_name(path)

	def where(self, node):
		return "%s:%s" % (self.rel, getattr(node, "lineno", "?"))

	# imports ----------------------------------------------------------------

	def is_addon_module(self, dotted):
		return dotted.split(".")[0] in ADDON_DIRS

	def check_import_module(self, node, dotted):
		top = dotted.split(".")[0]
		if top in sys.stdlib_module_names:
			return "std"
		if top in EXTERNAL:
			unchecked.append("%s: biblioteca externa '%s' (nao esta no codigo-fonte do NVDA)" % (self.where(node), dotted))
			return "external"
		if self.is_addon_module(dotted):
			if addon_module_file(dotted) is None:
				fail(self.where(node), "modulo do add-on '%s' nao existe" % dotted)
				return None
			return "addon"
		if module_file(self.src, dotted) is None:
			fail(self.where(node), "modulo do NVDA '%s' nao existe no codigo-fonte" % dotted)
			return None
		note("import %s" % dotted)
		return "nvda"

	def visit_Import(self, node):
		for alias in node.names:
			kind = self.check_import_module(node, alias.name)
			bound = alias.asname or alias.name.split(".")[0]
			if kind == "nvda":
				found = ("module", module_file(self.src, alias.name if alias.asname else bound), None)
				self.aliases[bound] = ("sym", found)
			elif kind == "std":
				self.aliases[bound] = ("std", None)

	def visit_ImportFrom(self, node):
		if node.level:
			base = resolve_relative(ROOT, self.path, node.level, node.module)
			self.check_addon_from(node, base)
			return
		module = node.module or ""
		kind = self.check_import_module(node, module)
		if kind in ("std", "external", None):
			for alias in node.names:
				self.aliases[alias.asname or alias.name] = ("std", None)
			return
		if kind == "addon":
			self.check_addon_from(node, module)
			return
		for alias in node.names:
			found = lookup_in(self.src, module, alias.name, 0)
			if not found:
				fail(self.where(node), "'%s' nao existe em %s (NVDA)" % (alias.name, module))
				continue
			note("from %s import %s" % (module, alias.name))
			self.aliases[alias.asname or alias.name] = ("sym", found)

	def check_addon_from(self, node, module):
		path = addon_module_file(module)
		if path is None:
			fail(self.where(node), "modulo do add-on '%s' nao existe" % module)
			return
		ns = addon_names(path)
		for alias in node.names:
			bound = alias.asname or alias.name
			if ns is not None and alias.name in ns.names:
				self.aliases[bound] = ("addon", None)
				continue
			if addon_module_file(module + "." + alias.name):
				self.aliases[bound] = ("addon", None)
				continue
			if ns is not None and any(addon_names(addon_module_file(m)) for m in ns.star if addon_module_file(m)):
				self.aliases[bound] = ("addon", None)
				continue
			fail(self.where(node), "'%s' nao existe em %s (add-on)" % (alias.name, module))

	# acessos a atributos --------------------------------------------------------

	def attribute_chain(self, node):
		chain = []
		while isinstance(node, ast.Attribute):
			chain.append(node.attr)
			node = node.value
		if isinstance(node, ast.Name):
			return node.id, list(reversed(chain))
		return None, []

	def visit_Attribute(self, node):
		root, chain = self.attribute_chain(node)
		if root and root in self.aliases and self.aliases[root][0] == "sym" and chain:
			self.check_chain(node, self.aliases[root][1], chain, root)
		self.generic_visit(node)

	def check_chain(self, node, found, chain, label):
		current = found
		pretty = label
		if current[0] == "assign" and (dotted_of(self.src, current[2]), label) in DYNAMIC_INSTANCES:
			cls_module, cls_name = DYNAMIC_INSTANCES[(dotted_of(self.src, current[2]), label)]
			cls = lookup_in(self.src, cls_module, cls_name, 0)
			if cls:
				current = ("instance", ClassInfo(self.src, cls[2], cls[1]), None)
		for index, attr in enumerate(chain):
			kind, data, path = current
			if kind == "module":
				dotted = dotted_of(self.src, data)
				nxt = lookup_in(self.src, dotted, attr, 0)
				if not nxt:
					fail(self.where(node), "%s.%s nao existe (modulo %s)" % (pretty, attr, dotted))
					return
				note("%s.%s" % (pretty, attr))
				if nxt[0] == "assign" and (dotted, attr) in DYNAMIC_INSTANCES:
					cls_module, cls_name = DYNAMIC_INSTANCES[(dotted, attr)]
					cls = lookup_in(self.src, cls_module, cls_name, 0)
					nxt = ("instance", ClassInfo(self.src, cls[2], cls[1]), None) if cls else nxt
				current = nxt
			elif kind in ("class", "assign", "instance"):
				info = None
				if kind == "instance":
					info = data
				elif kind == "class":
					info = ClassInfo(self.src, path, data)
				else:
					info = instance_class(self.src, current)
				if info is None:
					unchecked.append("%s: %s.%s (valor dinamico)" % (self.where(node), pretty, attr))
					return
				if not info.has(attr):
					if info.complete:
						fail(self.where(node), "%s.%s nao existe (classe %s)" % (pretty, attr, info.chain[0]))
					else:
						unchecked.append("%s: %s.%s (bases nao resolvidas)" % (self.where(node), pretty, attr))
					return
				note("%s.%s" % (pretty, attr))
				return  # membros de membros: nao resolviveis por ast
			elif kind == "func":
				ns = namespace(self.src, path)
				if (data.name, attr) in ns.func_attrs or attr.startswith("__"):
					note("%s.%s" % (pretty, attr))
				else:
					fail(self.where(node), "%s.%s: a funcao nao define esse atributo" % (pretty, attr))
				return
			pretty += "." + attr

	# classes e super() ----------------------------------------------------------

	def visit_ClassDef(self, node):
		info = None
		nvda_bases = False
		for base in node.bases:
			root, chain = self.attribute_chain(base) if isinstance(base, ast.Attribute) else (
				base.id if isinstance(base, ast.Name) else None,
				[],
			)
			if root and root in self.aliases and self.aliases[root][0] == "sym":
				nvda_bases = True
		if nvda_bases:
			info = self.build_class_info(node)
		self.class_stack.append((node, info))
		self.generic_visit(node)
		self.class_stack.pop()

	def build_class_info(self, node):
		"""ClassInfo das bases NVDA de ``node`` (as do proprio add-on contam como nao resolvidas)."""
		members = set()
		complete = True
		chain = []
		for base in node.bases:
			target = None
			root, attrs = self.attribute_chain(base) if isinstance(base, ast.Attribute) else (
				base.id if isinstance(base, ast.Name) else None,
				[],
			)
			if root and root in self.aliases and self.aliases[root][0] == "sym":
				current = self.aliases[root][1]
				for attr in attrs:
					if current[0] == "module":
						current = lookup_in(self.src, dotted_of(self.src, current[1]), attr, 0)
						if not current:
							break
				target = current
			if target and target[0] == "class":
				sub = ClassInfo(self.src, target[2], target[1])
				members |= sub.members
				complete = complete and sub.complete
				chain += sub.chain
			else:
				complete = False
		info = ClassInfo.__new__(ClassInfo)
		info.members, info.complete, info.chain = members, complete, chain or [node.name]
		return info

	def visit_Call(self, node):
		func = node.func
		# super().nome(...) e super().nome
		if (
			isinstance(func, ast.Attribute)
			and isinstance(func.value, ast.Call)
			and isinstance(func.value.func, ast.Name)
			and func.value.func.id == "super"
			and self.class_stack
		):
			self.check_super(node, func.attr)
		self.check_call_arguments(node)
		self.generic_visit(node)

	def check_super(self, node, attr):
		class_node, info = self.class_stack[-1]
		if info is None:
			return
		own = class_own_members(class_node)
		if attr in own and attr not in info.members:
			pass  # so existe no add-on: nao e do NVDA
		if info.has(attr):
			note("super().%s em %s" % (attr, class_node.name))
		elif info.complete:
			fail(self.where(node), "super().%s: nao existe na cadeia de %s (%s)" % (attr, class_node.name, " > ".join(info.chain)))
		else:
			unchecked.append("%s: super().%s (bases nao resolvidas)" % (self.where(node), attr))

	def visit_Attribute_super(self, node):
		return

	def check_call_arguments(self, node):
		found = None
		func = node.func
		if isinstance(func, ast.Name) and func.id in self.aliases and self.aliases[func.id][0] == "sym":
			found = self.aliases[func.id][1]
		elif isinstance(func, ast.Attribute):
			root, chain = self.attribute_chain(func)
			if root in self.aliases and self.aliases[root][0] == "sym":
				current = self.aliases[root][1]
				for attr in chain:
					if current and current[0] == "module":
						current = lookup_in(self.src, dotted_of(self.src, current[1]), attr, 0)
					else:
						current = None
						break
				found = current
		if not found or found[0] != "func":
			return
		args = found[1].args
		names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
		if args.kwarg is None:
			for keyword in node.keywords:
				if keyword.arg and keyword.arg not in names:
					fail(
						self.where(node),
						"%s(...) nao aceita o argumento '%s'" % (found[1].name, keyword.arg),
					)
		if args.vararg is None:
			max_pos = len(args.posonlyargs + args.args)
			if len(node.args) > max_pos:
				fail(self.where(node), "%s(...) recebe no maximo %d posicionais" % (found[1].name, max_pos))
		required = len(args.posonlyargs + args.args) - len(args.defaults)
		if not any(isinstance(a, ast.Starred) for a in node.args) and not node.keywords:
			if len(node.args) < required:
				fail(self.where(node), "%s(...) precisa de %d argumentos" % (found[1].name, required))
		note("chamada %s(...) confere com a assinatura" % found[1].name)


def check_instance_attrs(src):
	for (module, cls), names in INSTANCE_ATTRS.items():
		found = lookup_in(src, module, cls, 0)
		if not found or found[0] != "class":
			fail("INSTANCE_ATTRS", "classe %s.%s nao encontrada" % (module, cls))
			continue
		info = ClassInfo(src, found[2], found[1])
		for name in names:
			if info.has(name):
				note("%s.%s.%s" % (module, cls, name))
			elif info.complete:
				fail("INSTANCE_ATTRS", "%s.%s nao define '%s'" % (module, cls, name))
			else:
				unchecked.append("%s.%s.%s (bases nao resolvidas)" % (module, cls, name))


def check_hooks(src):
	for rel, snippet, why in HOOKS:
		path = os.path.join(src, *rel.split("/"))
		try:
			with open(path, encoding="utf-8") as handle:
				text = handle.read()
		except OSError:
			fail("HOOKS", "arquivo %s nao existe" % rel)
			continue
		if snippet in text:
			note("gancho %s: %s" % (rel, why))
		else:
			fail("HOOKS", "%s nao contem %r (%s)" % (rel, snippet, why))


def main():
	parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
	parser.add_argument("--fonte", default=DEFAULT_SRC, help="pasta source/ do NVDA 2026.2")
	parser.add_argument("-v", "--verbose", action="store_true")
	options = parser.parse_args()
	src = options.fonte
	if not os.path.isfile(os.path.join(src, "browseMode.py")):
		print("ERRO: nao achei o codigo-fonte do NVDA em %s" % src)
		return 2
	print("Codigo-fonte do NVDA: %s" % src)
	files = list(addon_files())
	for path in files:
		FileChecker(src, path).visit(parse(path))
	check_instance_attrs(src)
	check_hooks(src)
	print("Arquivos do add-on analisados: %d" % len(files))
	print("Verificacoes que conferiram: %d" % len(verified))
	if options.verbose:
		for item in sorted(set(verified)):
			print("  ok  " + item)
	if unchecked:
		print("Nao verificaveis por ast (%d):" % len(set(unchecked)))
		for item in sorted(set(unchecked)):
			print("  ?  " + item)
	if problems:
		print("PROBLEMAS (%d):" % len(problems))
		for item in problems:
			print("  X  " + item)
		return 1
	print("OK: toda API do NVDA usada existe no codigo-fonte do NVDA 2026.2.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
