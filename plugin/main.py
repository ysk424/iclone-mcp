import RLPy
from tcp_server import start_server

rl_plugin_info = {"ap": "iClone", "ap_version": "8.0"}

_server = None


def initialize_plugin():
    global _server
    _server = start_server()

    RLPy.RUi.ShowMessageBox(
        "iClone MCP",
        "Plugin started on localhost:54321",
        RLPy.EMsgButton_Ok,
    )
