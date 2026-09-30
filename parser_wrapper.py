import os
from lark import Lark
from indenter import TriaCIndenter

class TriaCParser:
	def __init__(self, grammar_filename="grammar.lark"):
		base_dir=os.path.dirname(os.path.abspath(__file__))
		grammar_path=os.path.join(base_dir, grammar_filename)
		
		if not os.path.exists(grammar_path):
			raise FileNotFoundError(f"Impossibile trovare il file di grammatica: {grammar_path}")

		self.indenter=TriaCIndenter()

		self.lark=Lark.open(
			grammar_path,
			parser="lalr",
			postlex=self.indenter,
			start="start",
			propagate_positions=True
		)
		
	def parse(self, code):
		normalized_code= code + "\n"
		return self.lark.parse(normalized_code)
