from service import abcService
import subprocess


class Service(abcService):

    name = 'apy-template'
    author = 'caph1993'
    version = '1.0'

    def start(self):
        subprocess.run(
            ['uvicorn', 'server:app', '--port', f'{self.port}'],
            check=True,
        )
        return
