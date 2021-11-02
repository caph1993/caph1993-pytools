from cp93pytools.audio import Sequence
from cp93pytools.methodtools import cached_property
from cp93pytools.process import MyProcess, test

test()

p = MyProcess([
    'python3', '-c', 'import time;[print(time.sleep(0.1)) for i in range(300)]'
])

p.run(capture_stdout=True)
