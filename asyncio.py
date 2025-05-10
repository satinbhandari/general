Thanks for the clarification. Given your constraints:

You're not in an async context when instantiating the class.

You can't await anything.

You still need to call an async setup method during class initialization without using asyncio.run(...) (because that closes the event loop and cleans up the session).


Here’s a workaround that bootstraps the async part during sync __init__, without closing the loop, by manually managing the event loop.


---

Solution: Start and keep an event loop running in a background thread

You create an event loop in a background thread and schedule your async setup in it. This way, the loop persists and doesn't clean up your async session.

import asyncio
import threading

class MyAsyncClass:
    def __init__(self):
        self.session = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Schedule the async method on the new loop
        future = asyncio.run_coroutine_threadsafe(self._async_setup(), self._loop)
        self.session = future.result()  # Waits for async setup to complete

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _async_setup(self):
        # Simulate async setup, e.g., creating a session
        await asyncio.sleep(1)  # replace with your real async call
        return "AsyncSessionObject"

    def shutdown(self):
        # Clean up the session and stop the loop when done
        def _stop():
            self._loop.stop()
        asyncio.run_coroutine_threadsafe(self._cleanup(), self._loop).result()
        self._loop.call_soon_threadsafe(_stop)
        self._thread.join()

    async def _cleanup(self):
        # Close async session here
        await asyncio.sleep(0.5)
        print("Session closed")


---

Usage (synchronous context):

my_obj = MyAsyncClass()
print(my_obj.session)  # Should print "AsyncSessionObject"
my_obj.shutdown()


---

This pattern lets you initialize and use async resources in a sync context without losing the session. It’s a bit lower-level, but safe and widely used in similar situations (e.g., background task management in sync apps).

Would you like me to adapt this to your exact session setup code?

