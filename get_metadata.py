import atexit
import pypi_json
import string
from domdf_python_tools.paths import PathPlus
import tqdm
import requests
from packaging.requirements import InvalidRequirement


hit_count = 0
miss_count = 0
# X-Cache HIT or MISS
changed_count = 0

cache_dir = PathPlus.cwd() / "search_cache"

regen = True
verbose = False

per_char_data = {}

def data_to_json(filename: PathPlus):
	data = {}
	last_key = None
	with filename.open() as fp:
		for line in fp.readlines():
			if line:
				try:
					name, summary_and_serial = line.split(" - ", 1)
					summary, serial = summary_and_serial.split("\0", 1)
					data[name] = {"summary": summary, "last_serial": serial.strip("\n")}
					last_key = name
				except ValueError:
					if last_key is not None:
						del data[last_key]
						last_key = None

	return data

for char in ("$" + string.ascii_lowercase):
	char_filename = cache_dir / char
	if char_filename.is_file():
		per_char_data[char] = data_to_json(char_filename)
	else:
		per_char_data[char] = {}



# Projects which are in the simple API only
# Ref: https://github.com/pypi/warehouse/issues/12207
bad_names = []

if (cache_dir / "bad_names.json").is_file():
	bad_names = (cache_dir / "bad_names.json").load_json()



def truncate(name: str) -> str:
        """
        Truncate summary to 100 chars max
        """

        filename_len = len(name)
        if filename_len > 100:
                return name[:97] + "..."
        else:
                return name

def write_cache_on_exit():

	for char in per_char_data:
		(cache_dir / char).write_text('')
		for project_name, project_data in per_char_data[char].items():
			(cache_dir / char).append_text(f"{project_name} - {truncate(project_data['summary'])}\0{project_data['last_serial']}\n")

	(cache_dir / "bad_names.json").dump_json(bad_names)


atexit.register(write_cache_on_exit)



response = requests.get("https://pypi.org/simple/", headers={"Accept": "application/vnd.pypi.simple.latest+json"})
response.raise_for_status()
simple_data = response.json()

with pypi_json.PyPIJSON() as json_client:

	for project in tqdm.tqdm(simple_data["projects"]):
		# print(project)
		name = project["name"]
		current_last_serial = project["_last-serial"]

		first_letter = name[0].lower()
		if first_letter not in string.ascii_letters:
			first_letter = "$"

		if name in bad_names:
			continue

		if name in per_char_data[first_letter] and per_char_data[first_letter][name]["last_serial"] == str(current_last_serial):
			continue
			
		changed_count += 1
		
		if verbose:
			print(f"Updating {name}")

		if name in per_char_data[first_letter]:
			print(per_char_data[first_letter][name]["last_serial"], str(current_last_serial))

		try:
			metadata = json_client.get_metadata(name)
		except InvalidRequirement:
			bad_names.append(name)
			continue
		except Exception as e:
			print(e)
			continue

		summary = (metadata.info["summary"] or '').replace("\n", " ")

		per_char_data[first_letter][name] = {"summary": summary, "last_serial": current_last_serial}
		# input(">")


print(f"Updated metadata for {changed_count} projects")
