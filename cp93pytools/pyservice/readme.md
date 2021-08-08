Objective:

Design a multi-process python API that shares memory among processes and can handle as many requests as possible. The API comes with a command line interface, CLI, that serves not only as example for how to implement a client, but also as a CLI for users like me.

Subscriptions:
 - Event subscriptions
 - Progress subscriptions

By design, queries that need to wait for an event or a server process will be closed and given a mechanism to subscribe.

Uploads and downloads:
 - Large uploads
 - Large downloads

By design, data transfer is done by chunks.


Step by step:

1. Robust CLI interface that spawns the server if not existent.

 - AppDirs, specially config data: automatic ports, current ports, etc.
 - PythonService: handle shutdown, start, restart, PID, etc.
 - General safety: ~handle unexpected deletion of AppDirs~, ~find and kill running instances in other ports~.

2. Flask? Falcon ASGI? (I like async)

