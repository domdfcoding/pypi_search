# stdlib
import concurrent.futures
import re
import string
import subprocess
import sys
from typing import Tuple

# 3rd party
import click
import platformdirs
from consolekit.options import flag_option
from domdf_python_tools.paths import PathPlus, in_directory
from domdf_python_tools.utils import divide, stderr_writer

"""
search regex...
		search performs a full text search on all available package lists for the regex pattern given. It searches the package names and the summary description for an occurrence of
		the regular expression and prints out the package name and summary. If --names-only is given then the summary is not searched, only the package name.

		Separate arguments can be used to specify multiple search patterns that are and'ed together.
"""

git_cache_dir = PathPlus(platformdirs.user_cache_dir("pypi-search", "domdfcoding"))
# cache_dir = PathPlus.cwd() / "search_cache"
cache_dir = git_cache_dir / "search_cache"

characters = '$' + string.ascii_lowercase


def find_matches(character, pattern, names_only: bool = False):
	"""
	Find matches for the search term in the search cache.

	:param character: Only search in projects starting with this character. ``$`` includes all other symbols. Case insensitive.
	:param pattern:
	:param names_only: Only search in names, don't search summaries as well.
	"""

	matches = []
	with (cache_dir / character).open() as fp:
		for line in fp.readlines():

			if names_only:
				line_to_search = divide(line, " - ")[0]
			else:
				line_to_search = line

			if re.search(pattern, line_to_search, flags=re.IGNORECASE):
				matches.append(line.split('\x00', 1)[0])

	return matches


@flag_option("--names-only")
@click.argument("regex", nargs=-1, required=True)
@click.command()
def main(regex: Tuple[str], names_only: bool = False):

	if not git_cache_dir.exists():
		stderr_writer("[INFO] Downloading metadata")
		subprocess.check_call([
				"git",
				"clone",
				"https://github.com/domdfcoding/pypi_search",
				git_cache_dir.as_posix(),
				])
	else:
		with in_directory(git_cache_dir):
			subprocess.check_call(["git", "pull"])

	search_term = regex[0]
	extra_search_terms = list(regex[1:])

	matches = []

	with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:

		future_to_character = {
				executor.submit(find_matches, char, search_term, names_only): char
				for char in characters
				}

		for future in concurrent.futures.as_completed(future_to_character):
			character = future_to_character[future]

			try:
				data = future.result()
			except Exception as exc:
				print(f"Exception for character {character!r}: {exc!s}")
			else:
				matches.extend(data)

	while extra_search_terms:
		search_term = extra_search_terms.pop(0)
		new_matches = []

		for match in matches:
			if re.search(search_term, match, flags=re.IGNORECASE):
				new_matches.append(match)

		matches = new_matches

	print('\n'.join(sorted(matches)))


if __name__ == "__main__":
	sys.exit(main())
