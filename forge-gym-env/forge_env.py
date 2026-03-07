import subprocess
import time
from py4j.java_gateway import JavaGateway, CallbackServerParameters

java_process = subprocess.Popen(["java", "-jar", "yourJavaApplication.jar"])
time.sleep(2)

# Now connect to the Java gateway with callbacks enabled.
gateway = JavaGateway(callback_server_parameters=CallbackServerParameters())
entry_point = gateway.entry_point

# Register your Python callback as shown earlier.
class MyPythonCallback(object):
    def onDemandFunction(self, msg):
        print("Python callback received:", msg)
        return "Response from Python: " + msg
    class Java:
        implements = ["com.mycompany.MyPythonInterface"]

python_callback = MyPythonCallback()
entry_point.registerCallback(python_callback)

response = entry_point.triggerPythonCallback("Test Message")
print("Response from Java:", response)

input("Press Enter to exit...")

# Optionally, terminate the Java process when done.
java_process.terminate()
