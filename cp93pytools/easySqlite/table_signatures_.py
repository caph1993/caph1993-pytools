from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from . import table_signatures
else:

    class IdentityProvider():

        def __getattribute__(self, _):
            return lambda f: f

    table_signatures = IdentityProvider()