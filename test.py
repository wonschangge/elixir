import re
from collections import namedtuple


print(re.match('^[a-zA-Z0-9_]+$', 'foo'))


Config = namedtuple('Config', 'project_dir')


Config(project_dir="path/to/project")



# def test_regex():
#     print(re.match('^[a-zA-Z0-9_]+$', 'foo'))
#     print(re.match(r'^[a-zA-Z0-9_.,:/-]+$', 'linux'))
#     print(re.match(r'^[a-zA-Z0-9_.,:/-]+$', 'linux:foo/bar,hello-world'))

# test_regex()